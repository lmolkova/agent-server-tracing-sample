from azure.search.documents.indexes.models import SearchIndex, SimpleField, SearchFieldDataType, VectorSearch, VectorSearchProfile, HnswAlgorithmConfiguration, AzureOpenAIVectorizer, AzureOpenAIVectorizerParameters, SemanticSearch, SemanticConfiguration, SemanticPrioritizedFields, SemanticField, SearchableField, ComplexField, SearchField
import os
import json


from chat.settings import EMBEDDING_MODEL, INDEX_CLIENT, INDEX_NAME, OPENAI_CLIENT, SEARCH_CLIENT

def create_search_index():
    return SearchIndex(
        name=INDEX_NAME,
        fields=[
            SimpleField(name="HotelId", type=SearchFieldDataType.String, key=True),
            SearchableField(name="HotelName", type=SearchFieldDataType.String, sortable=True),
            SearchField(name="HotelNameVector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), vector_search_dimensions=1536,
                vector_search_profile_name="vector-profile"),
            SearchableField(name="Description", type=SearchFieldDataType.String),
            SearchField(name="DescriptionVector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), vector_search_dimensions=1536,
                vector_search_profile_name="vector-profile"),
            SearchableField(
                    name="Description_fr",
                    type=SearchFieldDataType.String
                ),
            SearchField(name="Description_frvector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), vector_search_dimensions=1536,
                vector_search_profile_name="vector-profile"),
            SimpleField(
                name="IsDeleted",
                type=SearchFieldDataType.Boolean,
                searchable=False,
                filterable=True,
                sortable=True,
            ),
            SearchableField(
                name="Category",
                type=SearchFieldDataType.String,
                facetable=True,
                filterable=True,
                sortable=True,
            ),
            SearchableField(
                name="Tags",
                collection=True,
                type=SearchFieldDataType.String,
                facetable=True,
                filterable=True,
            ),
            SimpleField(
                name="ParkingIncluded",
                type=SearchFieldDataType.Boolean,
                facetable=True,
                filterable=True,
                sortable=True,
            ),
            SimpleField(
                name="LastRenovationDate",
                type=SearchFieldDataType.DateTimeOffset,
                facetable=True,
                filterable=True,
                sortable=True,
            ),
            SimpleField(
                name="Rating",
                type=SearchFieldDataType.Double,
                facetable=True,
                filterable=True,
                sortable=True,
            ),
            ComplexField(
                name="Address",
                fields=[
                    SearchableField(name="StreetAddress", type=SearchFieldDataType.String),
                    SearchableField(
                        name="City",
                        type=SearchFieldDataType.String,
                        facetable=True,
                        filterable=True,
                        sortable=True,
                    ),
                    SearchableField(
                        name="StateProvince",
                        type=SearchFieldDataType.String,
                        facetable=True,
                        filterable=True,
                        sortable=True,
                    ),
                    SearchableField(
                        name="PostalCode",
                        type=SearchFieldDataType.String,
                        facetable=True,
                        filterable=True,
                        sortable=True,
                    ),
                    SearchableField(
                        name="Country",
                        type=SearchFieldDataType.String,
                        facetable=True,
                        filterable=True,
                        sortable=True,
                    ),
                ],
            ),
            SimpleField(
                name="Location",
                type=SearchFieldDataType.GeographyPoint,
                filterable=True,
                sortable=True,
            ),
            ComplexField(
                name="Rooms",
                collection=True,
                fields=[
                    SearchableField(
                        name="Description",
                        type=SearchFieldDataType.String,
                        analyzer_name="en.lucene",
                    ),
                    SearchableField(
                        name="Description_fr",
                        type=SearchFieldDataType.String,
                        analyzer_name="fr.lucene",
                    ),
                    SearchableField(
                        name="Type",
                        type=SearchFieldDataType.String,
                        facetable=True,
                        filterable=True,
                    ),
                    SimpleField(
                        name="BaseRate",
                        type=SearchFieldDataType.Double,
                        facetable=True,
                        filterable=True,
                    ),
                    SearchableField(
                        name="BedOptions",
                        type=SearchFieldDataType.String,
                        facetable=True,
                        filterable=True,
                    ),
                    SimpleField(
                        name="SleepsCount",
                        type=SearchFieldDataType.Int32,
                        facetable=True,
                        filterable=True,
                    ),
                    SimpleField(
                        name="SmokingAllowed",
                        type=SearchFieldDataType.Boolean,
                        facetable=True,
                        filterable=True,
                    ),
                    SearchableField(
                        name="Tags",
                        type=SearchFieldDataType.String,
                        collection=True,
                        facetable=True,
                        filterable=True,
                    ),
                ],
            ),
        ],
        vector_search=VectorSearch(
            profiles=[
                VectorSearchProfile(
                    name="vector-profile",
                    algorithm_configuration_name="hnsw-algorithm",
                )
            ],
            algorithms=[
                HnswAlgorithmConfiguration(name="hnsw-algorithm")
            ],
        ),
        semantic_search=SemanticSearch(configurations=[
                SemanticConfiguration(
                    name="semantic-config",
                    prioritized_fields=SemanticPrioritizedFields(
                        title_field=SemanticField(field_name="HotelName"),
                        content_fields=[SemanticField(field_name="Description")],
                        keywords_fields=[SemanticField(field_name="Category")],
                    )
                )
            ]
        )
    )

def setup_search():
    index = create_search_index()
    INDEX_CLIENT.create_or_update_index(index)

def index_hotels():
    with open("hotels-small.json", "r", encoding="utf-8") as f:
        hotels = json.load(f)

    docs = []
    for hotel in hotels["value"]:
        hotel["DescriptionVector"] = OPENAI_CLIENT.embeddings.create(
            model=EMBEDDING_MODEL,
            input=hotel["Description"]
        ).data[0].embedding
        hotel["HotelNameVector"] = OPENAI_CLIENT.embeddings.create(
            model=EMBEDDING_MODEL,
            input=hotel["HotelName"]
        ).data[0].embedding

        docs.append(hotel)

    SEARCH_CLIENT.upload_documents(docs)
