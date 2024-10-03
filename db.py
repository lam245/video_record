from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

# Connect to the Elasticsearch server

es = Elasticsearch(
    hosts=["https://localhost:9200"],
    basic_auth=['elastic', 'J*BSr96bvcQ9cltdUdZ2'],
    verify_certs=False
)

# Function to create an index and add a document
def create_index(index_name):
    # Define a sample document
    document = {
        "name": "John Doe",
        "age": 30,
        "occupation": "Software Engineer"
    }

    # Create an index and add the document
    try:
        es.indices.create(index=index_name)
        print(f"Index '{index_name}' created successfully.")
    except Exception as e:
        print(f"Error creating index: {e}")
    
    # Add the document to the index
    response = es.index(index=index_name, id=1, document=document)
    print("Document added:", response)

# Function to search in the index
def search_index(index_name):
    try:
        # Perform a search query
        response = es.search(index=index_name, query={"match_all": {}})
        print("Search results:", response["hits"]["hits"])
    except NotFoundError:
        print(f"Index '{index_name}' not found.")
    except Exception as e:
        print(f"Search error: {e}")

# Function to delete the index
def delete_index(index_name):
    try:
        es.indices.delete(index=index_name)
        print(f"Index '{index_name}' deleted successfully.")
    except NotFoundError:
        print(f"Index '{index_name}' not found.")
    except Exception as e:
        print(f"Error deleting index: {e}")

if __name__ == "__main__":
    index_name = "test_index"

    # Test Elasticsearch
    create_index(index_name)   # Create an index and add a document
    search_index(index_name)   # Search the index
    delete_index(index_name)   # Delete the index
