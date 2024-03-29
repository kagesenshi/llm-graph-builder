from langchain_community.graphs import Neo4jGraph
from dotenv import load_dotenv
from langchain.schema import Document
from src.make_relationships import create_source_chunk_entity_relationship
import logging
import re
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from typing import List
import uuid
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_google_vertexai import ChatVertexAI
import vertexai
from typing import Any, List, Optional, Sequence
from langchain_community.graphs.graph_document import GraphDocument, Node, Relationship
from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain.pydantic_v1 import BaseModel
from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate
from typing import List
from langchain_core.pydantic_v1 import BaseModel, Field
import google.auth 


load_dotenv()
logging.basicConfig(format='%(asctime)s - %(message)s',level='INFO')

system_prompt = (
    "# Knowledge Graph Instructions for GPT-4\n"
    "## 1. Overview\n"
    "You are a top-tier algorithm designed for extracting information in structured "
    "formats to build a knowledge graph.\n"
    "Try to capture as much information from the text as possible without "
    "sacrifing accuracy. Do not add any information that is not explicitly "
    "mentioned in the text\n"
    "- **Nodes** represent entities and concepts.\n"
    "- The aim is to achieve simplicity and clarity in the knowledge graph, making it\n"
    "accessible for a vast audience.\n"
    "## 2. Labeling Nodes\n"
    "- **Consistency**: Ensure you use available types for node labels.\n"
    "Ensure you use basic or elementary types for node labels.\n"
    "- For example, when you identify an entity representing a person, "
    "always label it as **'person'**. Avoid using more specific terms "
    "like 'mathematician' or 'scientist'"
    "  - **Node IDs**: Never utilize integers as node IDs. Node IDs should be "
    "names or human-readable identifiers found in the text.\n"
    "- **Relationships** represent connections between entities or concepts.\n"
    "Ensure consistency and generality in relationship types when constructing "
    "knowledge graphs. Instead of using specific and momentary types "
    "such as 'BECAME_PROFESSOR', use more general and timeless relationship types "
    "like 'PROFESSOR'. Make sure to use general and timeless relationship types!\n"
    "## 3. Coreference Resolution\n"
    "- **Maintain Entity Consistency**: When extracting entities, it's vital to "
    "ensure consistency.\n"
    'If an entity, such as "John Doe", is mentioned multiple times in the text '
    'but is referred to by different names or pronouns (e.g., "Joe", "he"),'
    "always use the most complete identifier for that entity throughout the "
    'knowledge graph. In this example, use "John Doe" as the entity ID.\n'
    "Remember, the knowledge graph should be coherent and easily understandable, "
    "so maintaining consistency in entity references is crucial.\n"
    "## 4. Strict Compliance\n"
    "Adhere to the rules strictly. Non-compliance will result in termination."
)

default_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            system_prompt,
        ),
        (
            "human",
            (
                "Tip: Make sure to answer in the correct format and do "
                "not include any explanations. "
                "Use the given format to extract information from the "
                "following input: {input}"
            ),
        ),
    ]
)


def optional_enum_field(
    enum_values: Optional[List[str]] = None,
    description: str = "",
    is_rel: bool = False,
    **field_kwargs: Any,
) -> Any:
    """Utility function to conditionally create a field with an enum constraint."""
    if enum_values:
        return Field(
            ...,
            enum=enum_values,
            description=f"{description}. Available options are {enum_values}",
            **field_kwargs,
        )
    else:
        node_info = (
            "Ensure you use basic or elementary types for node labels.\n"
            "For example, when you identify an entity representing a person, "
            "always label it as **'Person'**. Avoid using more specific terms "
            "like 'Mathematician' or 'Scientist'"
        )
        rel_info = (
            "Instead of using specific and momentary types such as "
            "'BECAME_PROFESSOR', use more general and timeless relationship types like "
            "'PROFESSOR'. However, do not sacrifice any accuracy for generality"
        )
        additional_info = rel_info if is_rel else node_info
        return Field(..., description=description + additional_info, **field_kwargs)


def create_simple_model(
    node_labels: Optional[List[str]] = None, rel_types: Optional[List[str]] = None
) -> Any:
    """
    Simple model allows to limit node and/or relationship types.
    Doesn't have any node or relationship properties.
    """
    class SimpleRelationship(BaseModel):
        """Represents a directed relationship between two nodes in a graph."""
        start_node_id: str = optional_enum_field(
            node_labels, description="The type or label of the start node."
        )
        start_node_type: str = Field(description="Mandatory type of the start node of the relationship.")
        end_node_id: str = Field(description="Name or human-readable unique identifier of end node")
        end_node_type: str = optional_enum_field(
            node_labels, description="The type or label of the end node."
        )
        type: str = optional_enum_field(
            rel_types, description="The type of the relationship.", is_rel=True
        )

    class DynamicGraph(BaseModel):
        """Represents a graph document consisting of nodes and relationships."""

        relationships: Optional[List[SimpleRelationship]] = Field(
            description="List of relationships"
        )

    return DynamicGraph

def map_to_base_relationship(rel: Any) -> Relationship:
    """Map the SimpleRelationship to the base Relationship."""
    source = Node(id=rel.start_node_id.title(), type=rel.start_node_type.capitalize())
    target = Node(id=rel.end_node_id.title(), type=rel.end_node_type.capitalize())
    return Relationship(
        source=source, target=target, type=rel.type.replace(" ", "_").upper()
    )

class GeminiLLMGraphTransformer: 
    def __init__(
        self,
        llm: BaseLanguageModel,
        allowed_nodes: List[str] = [],
        allowed_relationships: List[str] = [],
        prompt: Optional[ChatPromptTemplate] = default_prompt,
        strict_mode: bool = True,
    ) -> None:
        if not hasattr(llm, "with_structured_output"):
            raise ValueError(
                "The specified LLM does not support the 'with_structured_output'. "
                "Please ensure you are using an LLM that supports this feature."
            )
        self.allowed_nodes = allowed_nodes
        self.allowed_relationships = allowed_relationships
        self.strict_mode = strict_mode

        # Define chain
        schema = create_simple_model(allowed_nodes, allowed_relationships)
        structured_llm = llm.with_structured_output(schema)
        self.chain = default_prompt | structured_llm


    def process_response(self, document: Document) -> GraphDocument:
            """
            Processes a single document, transforming it into a graph document using
            an LLM based on the model's schema and constraints.
            """
            text = document.page_content
            raw_schema = self.chain.invoke({"input": text})
            # if raw_schema.nodes:
            #     nodes = [map_to_base_node(node) for node in raw_schema.nodes]
            # else:
            #     nodes = []
            if raw_schema.relationships:
                relationships = [
                    map_to_base_relationship(rel) for rel in raw_schema.relationships
                ]
            else:
                relationships = []

            # Strict mode filtering
            if self.strict_mode and (self.allowed_nodes or self.allowed_relationships):
                if self.allowed_relationships and self.allowed_nodes:
                    nodes = [node for node in nodes if node.type in self.allowed_nodes]
                    relationships = [
                        rel
                        for rel in relationships
                        if rel.type in self.allowed_relationships
                        and rel.source.type in self.allowed_nodes
                        and rel.target.type in self.allowed_nodes
                    ]
                elif self.allowed_nodes and not self.allowed_relationships:
                    nodes = [node for node in nodes if node.type in self.allowed_nodes]
                    relationships = [
                        rel
                        for rel in relationships
                        if rel.source.type in self.allowed_nodes
                        and rel.target.type in self.allowed_nodes
                    ]
                if self.allowed_relationships and not self.allowed_nodes:
                    relationships = [
                        rel
                        for rel in relationships
                        if rel.type in self.allowed_relationships
                    ]

            graph_document = GraphDocument(
                nodes=nodes, relationships=relationships, source=document
            )
            return graph_document

    def convert_to_graph_documents(
            self, documents: Sequence[Document]
        ) -> List[GraphDocument]:
            """Convert a sequence of documents into graph documents.

            Args:
                documents (Sequence[Document]): The original documents.
                **kwargs: Additional keyword arguments.

            Returns:
                Sequence[GraphDocument]: The transformed documents as graphs.
            """
            results = []
            for document in documents:
                graph_document = self.process_response(document)
                results.append(graph_document)
            return results    

def get_graph_from_Gemini(model_version,
                            graph: Neo4jGraph,
                            chunks: List[Document]):
    """
        Extract graph from OpenAI and store it in database. 
        This is a wrapper for extract_and_store_graph
                                
        Args:
            model_version : identify the model of LLM
            graph: Neo4jGraph to be extracted.
            chunks: List of chunk documents created from input file
        Returns: 
            List of langchain GraphDocument - used to generate graph
    """
    logging.info(f"Get grapgDocuments from {model_version}")
    futures = []
    graph_document_list = []
    location = "us-central1"
    redentials, project_id = google.auth.default()
    vertexai.init(project=project_id, location=location)
    llm = ChatVertexAI(model_name=model_version,
                    convert_system_message_to_human=True,
                    temperature=0
                )
    llm_transformer = GeminiLLMGraphTransformer(llm=llm)
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        for chunk_document in chunks:
            futures.append(executor.submit(llm_transformer.convert_to_graph_documents,[chunk_document]))   
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            graph_document = future.result()
            for node in graph_document[0].nodes:
                node.id = node.id.title().replace(' ','_')
                #replace all non alphanumeric characters and spaces with underscore
                node.type = re.sub(r'[^\w]+', '_', node.type.capitalize())
            graph_document_list.append(graph_document[0])
        
        graph.add_graph_documents(graph_document_list)
    return  graph_document_list