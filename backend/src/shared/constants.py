MODEL_VERSIONS = {
        "openai-gpt-3.5": "gpt-3.5-turbo-0125",
        "gemini-1.0-pro": "gemini-1.0-pro-001",
        "gemini-1.5-pro": "gemini-1.5-pro-002",
        "gemini-1.5-flash": "gemini-1.5-flash-002",
        "openai-gpt-4": "gpt-4-turbo-2024-04-09",
        "diffbot" : "gpt-4-turbo-2024-04-09",
        "openai-gpt-4o-mini": "gpt-4o-mini-2024-07-18",
        "openai-gpt-4o":"gpt-4o-2024-08-06",
        "groq-llama3" : "llama3-70b-8192"
         }
OPENAI_MODELS = ["openai-gpt-3.5", "openai-gpt-4o", "openai-gpt-4o-mini"]
GEMINI_MODELS = ["gemini-1.0-pro", "gemini-1.5-pro", "gemini-1.5-flash"]
GROQ_MODELS = ["groq-llama3"]
BUCKET_UPLOAD = 'llm-graph-builder-upload'
BUCKET_FAILED_FILE = 'llm-graph-builder-failed'
PROJECT_ID = 'llm-experiments-387609' 
GRAPH_CHUNK_LIMIT = 50 


#query 
GRAPH_QUERY = """
MATCH docs = (d:Document) 
WHERE d.fileName IN $document_names
WITH docs, d ORDER BY d.createdAt DESC
// fetch chunks for documents, currently with limit
CALL {{
  WITH d
  OPTIONAL MATCH chunks=(d)<-[:PART_OF|FIRST_CHUNK]-(c:Chunk)
  RETURN c, chunks LIMIT {graph_chunk_limit}
}}

WITH collect(distinct docs) as docs, collect(distinct chunks) as chunks, collect(distinct c) as selectedChunks
WITH docs, chunks, selectedChunks
// select relationships between selected chunks
WITH *, 
[ c in selectedChunks | [p=(c)-[:NEXT_CHUNK|SIMILAR]-(other) WHERE other IN selectedChunks | p]] as chunkRels

// fetch entities and relationships between entities
CALL {{
  WITH selectedChunks
  UNWIND selectedChunks as c

  OPTIONAL MATCH entities=(c:Chunk)-[:HAS_ENTITY]->(e)
  OPTIONAL MATCH entityRels=(e)--(e2:!Chunk) WHERE exists {{
    (e2)<-[:HAS_ENTITY]-(other) WHERE other IN selectedChunks
  }}
  RETURN entities , entityRels, collect(DISTINCT e) as entity
}}
WITH  docs,chunks,chunkRels, collect(entities) as entities, collect(entityRels) as entityRels, entity

WITH *

CALL {{
  with entity
  unwind entity as n
  OPTIONAL MATCH community=(n:__Entity__)-[:IN_COMMUNITY]->(p:__Community__)
  OPTIONAL MATCH parentcommunity=(p)-[:PARENT_COMMUNITY*]->(p2:__Community__) 
  return collect(community) as communities , collect(parentcommunity) as parentCommunities
}}

WITH apoc.coll.flatten(docs + chunks + chunkRels + entities + entityRels + communities + parentCommunities, true) as paths

// distinct nodes and rels
CALL {{ WITH paths UNWIND paths AS path UNWIND nodes(path) as node WITH distinct node 
       RETURN collect(node /* {{.*, labels:labels(node), elementId:elementId(node), embedding:null, text:null}} */) AS nodes }}
CALL {{ WITH paths UNWIND paths AS path UNWIND relationships(path) as rel RETURN collect(distinct rel) AS rels }}  
RETURN nodes, rels

"""

CHUNK_QUERY = """
match (chunk:Chunk) where chunk.id IN $chunksIds

MATCH (chunk)-[:PART_OF]->(d:Document)
CALL {WITH chunk
MATCH (chunk)-[:HAS_ENTITY]->(e) 
MATCH path=(e)(()-[rels:!HAS_ENTITY&!PART_OF]-()){0,2}(:!Chunk &! Document &! `__Community__`) 
UNWIND rels as r
RETURN collect(distinct r) as rels
}
WITH d, collect(distinct chunk) as chunks, apoc.coll.toSet(apoc.coll.flatten(collect(rels))) as rels
RETURN d as doc, [chunk in chunks | chunk {.*, embedding:null}] as chunks,
       [r in rels | {startNode:{element_id:elementId(startNode(r)), labels:labels(startNode(r)), properties:{id:startNode(r).id,description:startNode(r).description}},
                     endNode:{element_id:elementId(endNode(r)), labels:labels(endNode(r)), properties:{id:endNode(r).id,description:endNode(r).description}},
                     relationship: {type:type(r), element_id:elementId(r)}}] as entities
"""

## CHAT SETUP
CHAT_MAX_TOKENS = 1000
CHAT_SEARCH_KWARG_K = 10
CHAT_SEARCH_KWARG_SCORE_THRESHOLD = 0.5
CHAT_DOC_SPLIT_SIZE = 3000
CHAT_EMBEDDING_FILTER_SCORE_THRESHOLD = 0.10
CHAT_TOKEN_CUT_OFF = {
     ("openai-gpt-3.5",'azure_ai_gpt_35',"gemini-1.0-pro","gemini-1.5-pro","gemini-1.5-flash","groq-llama3",'groq_llama3_70b','anthropic_claude_3_5_sonnet','fireworks_llama_v3_70b','bedrock_claude_3_5_sonnet', ) : 4, 
     ("openai-gpt-4","diffbot" ,'azure_ai_gpt_4o',"openai-gpt-4o", "openai-gpt-4o-mini") : 28,
     ("ollama_llama3") : 2  
} 


CHAT_TOKEN_CUT_OFF = {
     ("openai-gpt-3.5",'azure_ai_gpt_35',"gemini-1.0-pro","gemini-1.5-pro", "gemini-1.5-flash","groq-llama3",'groq_llama3_70b','anthropic_claude_3_5_sonnet','fireworks_llama_v3_70b','bedrock_claude_3_5_sonnet', ) : 4, 
     ("openai-gpt-4","diffbot" ,'azure_ai_gpt_4o',"openai-gpt-4o", "openai-gpt-4o-mini") : 28,
     ("ollama_llama3") : 2  
} 

### CHAT TEMPLATES 
CHAT_SYSTEM_TEMPLATE = """
You are an AI-powered question-answering agent. Your task is to provide accurate and comprehensive responses to user queries based on the given context, chat history, and available resources.

### Response Guidelines:
1. **Direct Answers**: Provide clear and thorough answers to the user's queries without headers unless requested. Avoid speculative responses.
2. **Utilize History and Context**: Leverage relevant information from previous interactions, the current user input, and the context provided below.
3. **No Greetings in Follow-ups**: Start with a greeting in initial interactions. Avoid greetings in subsequent responses unless there's a significant break or the chat restarts.
4. **Admit Unknowns**: Clearly state if an answer is unknown. Avoid making unsupported statements.
5. **Avoid Hallucination**: Only provide information based on the context provided. Do not invent information.
6. **Response Length**: Keep responses concise and relevant. Aim for clarity and completeness within 4-5 sentences unless more detail is requested.
7. **Tone and Style**: Maintain a professional and informative tone. Be friendly and approachable.
8. **Error Handling**: If a query is ambiguous or unclear, ask for clarification rather than providing a potentially incorrect answer.
9. **Fallback Options**: If the required information is not available in the provided context, provide a polite and helpful response. Example: "I don't have that information right now." or "I'm sorry, but I don't have that information. Is there something else I can help with?"
10. **Context Availability**: If the context is empty, do not provide answers based solely on internal knowledge. Instead, respond appropriately by indicating the lack of information.


**IMPORTANT** : DO NOT ANSWER FROM YOUR KNOWLEDGE BASE USE THE BELOW CONTEXT

### Context:
<context>
{context}
</context>

### Example Responses:
User: Hi 
AI Response: 'Hello there! How can I assist you today?'

User: "What is Langchain?"
AI Response: "Langchain is a framework that enables the development of applications powered by large language models, such as chatbots. It simplifies the integration of language models into various applications by providing useful tools and components."

User: "Can you explain how to use memory management in Langchain?"
AI Response: "Langchain's memory management involves utilizing built-in mechanisms to manage conversational context effectively. It ensures that the conversation remains coherent and relevant by maintaining the history of interactions and using it to inform responses."

User: "I need help with PyCaret's classification model."
AI Response: "PyCaret simplifies the process of building and deploying machine learning models. For classification tasks, you can use PyCaret's setup function to prepare your data. After setup, you can compare multiple models to find the best one, and then fine-tune it for better performance."

User: "What can you tell me about the latest realtime trends in AI?"
AI Response: "I don't have that information right now. Is there something else I can help with?"

Note: This system does not generate answers based solely on internal knowledge. It answers from the information provided in the user's current and previous inputs, and from the context.
"""

QUESTION_TRANSFORM_TEMPLATE = "Given the below conversation, generate a search query to look up in order to get information relevant to the conversation. Only respond with the query, nothing else." 

## CHAT QUERIES 
VECTOR_SEARCH_QUERY = """
WITH node AS chunk, score
MATCH (chunk)-[:PART_OF]->(d:Document)
WITH d, collect(distinct {chunk: chunk, score: score}) as chunks, avg(score) as avg_score
WITH d, avg_score, 
     [c in chunks | c.chunk.text] as texts, 
     [c in chunks | {id: c.chunk.id, score: c.score}] as chunkdetails
WITH d, avg_score, chunkdetails,
     apoc.text.join(texts, "\n----\n") as text
RETURN text, avg_score AS score, 
       {source: COALESCE(CASE WHEN d.url CONTAINS "None" THEN d.fileName ELSE d.url END, d.fileName), chunkdetails: chunkdetails} as metadata
""" 

VECTOR_GRAPH_SEARCH_ENTITY_LIMIT = 25

VECTOR_GRAPH_SEARCH_QUERY = """
WITH node as chunk, score
// find the document of the chunk
MATCH (chunk)-[:PART_OF]->(d:Document)
// fetch entities
CALL { WITH chunk
// entities connected to the chunk
// todo only return entities that are actually in the chunk, remember we connect all extracted entities to all chunks
MATCH (chunk)-[:HAS_ENTITY]->(e)

// depending on match to query embedding either 1 or 2 step expansion
WITH CASE WHEN true // vector.similarity.cosine($embedding, e.embedding ) <= 0.95
THEN 
collect { MATCH path=(e)(()-[rels:!HAS_ENTITY&!PART_OF]-()){0,1}(:!Chunk&!Document) RETURN path }
ELSE 
collect { MATCH path=(e)(()-[rels:!HAS_ENTITY&!PART_OF]-()){0,2}(:!Chunk&!Document) RETURN path } 
END as paths

RETURN collect{ unwind paths as p unwind relationships(p) as r return distinct r} as rels,
collect{ unwind paths as p unwind nodes(p) as n return distinct n} as nodes
}
// aggregate chunk-details and de-duplicate nodes and relationships
WITH d, collect(DISTINCT {chunk: chunk, score: score}) AS chunks, avg(score) as avg_score, apoc.coll.toSet(apoc.coll.flatten(collect(rels))) as rels,

// TODO sort by relevancy (embeddding comparision?) cut off after X (e.g. 25) nodes?
apoc.coll.toSet(apoc.coll.flatten(collect(
                [r in rels |[startNode(r),endNode(r)]]),true)) as nodes

// generate metadata and text components for chunks, nodes and relationships
WITH d, avg_score,
     [c IN chunks | c.chunk.text] AS texts, 
     [c IN chunks | {id: c.chunk.id, score: c.score}] AS chunkdetails,  
  apoc.coll.sort([n in nodes | 

coalesce(apoc.coll.removeAll(labels(n),['__Entity__'])[0],"") +":"+ 
n.id + (case when n.description is not null then " ("+ n.description+")" else "" end)]) as nodeTexts,
	apoc.coll.sort([r in rels 
    // optional filter if we limit the node-set
    // WHERE startNode(r) in nodes AND endNode(r) in nodes 
  | 
coalesce(apoc.coll.removeAll(labels(startNode(r)),['__Entity__'])[0],"") +":"+ 
startNode(r).id +
" " + type(r) + " " + 
coalesce(apoc.coll.removeAll(labels(endNode(r)),['__Entity__'])[0],"") +":" + 
endNode(r).id
]) as relTexts

// combine texts into response-text
WITH d, avg_score,chunkdetails,
"Text Content:\n" +
apoc.text.join(texts,"\n----\n") +
"\n----\nEntities:\n"+
apoc.text.join(nodeTexts,"\n") +
"\n----\nRelationships:\n"+
apoc.text.join(relTexts,"\n")

as text
RETURN text, avg_score as score, {length:size(text), source: COALESCE( CASE WHEN d.url CONTAINS "None" THEN d.fileName ELSE d.url END, d.fileName), chunkdetails: chunkdetails} AS metadata
"""





RETURN text, avg_score as score, {{length:size(text), source: COALESCE( CASE WHEN d.url CONTAINS "None" THEN d.fileName ELSE d.url END, d.fileName), chunkdetails: chunkdetails}} AS metadata
"""

### Local community search
LOCAL_COMMUNITY_TOP_K = 10
LOCAL_COMMUNITY_TOP_CHUNKS = 3
LOCAL_COMMUNITY_TOP_COMMUNITIES = 3
LOCAL_COMMUNITY_TOP_OUTSIDE_RELS = 10

LOCAL_COMMUNITY_SEARCH_QUERY = """
WITH collect(node) AS nodes, 
     avg(score) AS score, 
     collect({{id: elementId(node), score: score}}) AS metadata

WITH score, nodes, metadata,

     collect {{
         UNWIND nodes AS n
         MATCH (n)<-[:HAS_ENTITY]->(c:Chunk)
         WITH c, count(distinct n) AS freq
         RETURN c
         ORDER BY freq DESC
         LIMIT {topChunks}
     }} AS chunks,

     collect {{
         UNWIND nodes AS n
         MATCH (n)-[:IN_COMMUNITY]->(c:__Community__)
         WITH c, c.community_rank AS rank, c.weight AS weight
         RETURN c
         ORDER BY rank, weight DESC
         LIMIT {topCommunities}
     }} AS communities,

     collect {{
         UNWIND nodes AS n
         UNWIND nodes AS m
         MATCH (n)-[r]->(m)
         RETURN DISTINCT r
         // TODO: need to add limit
     }} AS rels,

     collect {{
         UNWIND nodes AS n
         MATCH path = (n)-[r]-(m:__Entity__)
         WHERE NOT m IN nodes
         WITH m, collect(distinct r) AS rels, count(*) AS freq
         ORDER BY freq DESC 
         LIMIT {topOutsideRels}
         WITH collect(m) AS outsideNodes, apoc.coll.flatten(collect(rels)) AS rels
         RETURN {{ nodes: outsideNodes, rels: rels }}
     }} AS outside
"""

LOCAL_COMMUNITY_SEARCH_QUERY_SUFFIX = """
RETURN {
  chunks: [c IN chunks | c.text],
  communities: [c IN communities | c.summary],
  entities: [
    n IN nodes | 
    CASE 
      WHEN size(labels(n)) > 1 THEN 
        apoc.coll.removeAll(labels(n), ["__Entity__"])[0] + ":" + n.id + " " + coalesce(n.description, "")
      ELSE 
        n.id + " " + coalesce(n.description, "")
    END
  ],
  relationships: [
    r IN rels | 
    startNode(r).id + " " + type(r) + " " + endNode(r).id
  ],
  outside: {
    nodes: [
      n IN outside[0].nodes | 
      CASE 
        WHEN size(labels(n)) > 1 THEN 
          apoc.coll.removeAll(labels(n), ["__Entity__"])[0] + ":" + n.id + " " + coalesce(n.description, "")
        ELSE 
          n.id + " " + coalesce(n.description, "")
      END
    ],
    relationships: [
      r IN outside[0].rels | 
      CASE 
        WHEN size(labels(startNode(r))) > 1 THEN 
          apoc.coll.removeAll(labels(startNode(r)), ["__Entity__"])[0] + ":" + startNode(r).id + " "
        ELSE 
          startNode(r).id + " "
      END + 
      type(r) + " " +
      CASE 
        WHEN size(labels(endNode(r))) > 1 THEN 
          apoc.coll.removeAll(labels(endNode(r)), ["__Entity__"])[0] + ":" + endNode(r).id
        ELSE 
          endNode(r).id
      END
    ]
  }
} AS text,
score,
{entities: metadata} AS metadata
"""

LOCAL_COMMUNITY_DETAILS_QUERY_PREFIX = """
UNWIND $entityIds as id
MATCH (node) WHERE elementId(node) = id
WITH node, 1.0 as score
"""
LOCAL_COMMUNITY_DETAILS_QUERY_SUFFIX = """
WITH *
UNWIND chunks AS c
MATCH (c)-[:PART_OF]->(d:Document)
RETURN 
    [
        c {
            .*,
            embedding: null,
            fileName: d.fileName,
            fileSource: d.fileSource
        }
    ] AS chunks,
    [
        community IN communities | 
        community {
            .*,
            embedding: null
        }
    ] AS communities,
    [
        node IN nodes + outside[0].nodes | 
        {
            element_id: elementId(node),
            labels: labels(node),
            properties: {
                id: node.id,
                description: node.description
            }
        }
    ] AS nodes, 
    [
        r IN rels + outside[0].rels | 
        {
            startNode: {
                element_id: elementId(startNode(r)),
                labels: labels(startNode(r)),
                properties: {
                    id: startNode(r).id,
                    description: startNode(r).description
                }
            },
            endNode: {
                element_id: elementId(endNode(r)),
                labels: labels(endNode(r)),
                properties: {
                    id: endNode(r).id,
                    description: endNode(r).description
                }
            },
            relationship: {
                type: type(r),
                element_id: elementId(r)
            }
        }
    ] AS entities
"""

CHAT_MODE_CONFIG_MAP= {
        "vector": {
            "retrieval_query": VECTOR_SEARCH_QUERY,
            "index_name": "vector",
            "keyword_index": None,
            "document_filter": True
        },
        "fulltext": {
            "retrieval_query": VECTOR_SEARCH_QUERY,  
            "index_name": "vector",  
            "keyword_index": "keyword", 
            "document_filter": False
        },
        "entity search+vector": {
            "retrieval_query": LOCAL_COMMUNITY_SEARCH_QUERY.format(topChunks=LOCAL_COMMUNITY_TOP_CHUNKS,
                                                                   topCommunities=LOCAL_COMMUNITY_TOP_COMMUNITIES,
                                                                   topOutsideRels=LOCAL_COMMUNITY_TOP_OUTSIDE_RELS)+LOCAL_COMMUNITY_SEARCH_QUERY_SUFFIX,
            "index_name": "entity_vector",
            "keyword_index": None,
            "document_filter": False
        },
        "graph+vector": {
            "retrieval_query": VECTOR_GRAPH_SEARCH_QUERY.format(no_of_entites=VECTOR_GRAPH_SEARCH_ENTITY_LIMIT),
            "index_name": "vector",
            "keyword_index": None,
            "document_filter": True
        },
        "graph+vector+fulltext": {
            "retrieval_query": VECTOR_GRAPH_SEARCH_QUERY.format(no_of_entites=VECTOR_GRAPH_SEARCH_ENTITY_LIMIT),
            "index_name": "vector",
            "keyword_index": "keyword",
            "document_filter": False
        },
        "default": {
            "retrieval_query": VECTOR_SEARCH_QUERY,
            "index_name": "vector",
            "keyword_index": None,
            "document_filter": True
        }
    }
YOUTUBE_CHUNK_SIZE_SECONDS = 60

QUERY_TO_GET_CHUNKS = """
            MATCH (d:Document)
            WHERE d.fileName = $filename
            WITH d
            OPTIONAL MATCH (d)<-[:PART_OF|FIRST_CHUNK]-(c:Chunk)
            RETURN c.id as id, c.text as text, c.position as position 
            """
            
QUERY_TO_DELETE_EXISTING_ENTITIES = """
                                MATCH (d:Document {fileName:$filename})
                                WITH d
                                MATCH (d)<-[:PART_OF]-(c:Chunk)
                                WITH d,c
                                MATCH (c)-[:HAS_ENTITY]->(e)
                                WHERE NOT EXISTS { (e)<-[:HAS_ENTITY]-()<-[:PART_OF]-(d2:Document) }
                                DETACH DELETE e
                                """   

QUERY_TO_GET_LAST_PROCESSED_CHUNK_POSITION="""
                              MATCH (d:Document)
                              WHERE d.fileName = $filename
                              WITH d
                              MATCH (c:Chunk) WHERE c.embedding is null 
                              RETURN c.id as id,c.position as position 
                              ORDER BY c.position LIMIT 1
                              """   
QUERY_TO_GET_LAST_PROCESSED_CHUNK_WITHOUT_ENTITY = """
                              MATCH (d:Document)
                              WHERE d.fileName = $filename
                              WITH d
                              MATCH (d)<-[:PART_OF]-(c:Chunk) WHERE NOT exists {(c)-[:HAS_ENTITY]->()}
                              RETURN c.id as id,c.position as position 
                              ORDER BY c.position LIMIT 1
                              """
QUERY_TO_GET_NODES_AND_RELATIONS_OF_A_DOCUMENT = """
                              MATCH (d:Document)<-[:PART_OF]-(:Chunk)-[:HAS_ENTITY]->(e) where d.fileName=$filename
                              OPTIONAL MATCH (d)<-[:PART_OF]-(:Chunk)-[:HAS_ENTITY]->(e2:!Chunk)-[rel]-(e)
                              RETURN count(DISTINCT e) as nodes, count(DISTINCT rel) as rels
                              """                              

START_FROM_BEGINNING  = "start_from_beginning"     
DELETE_ENTITIES_AND_START_FROM_BEGINNING = "delete_entities_and_start_from_beginning"
START_FROM_LAST_PROCESSED_POSITION = "start_from_last_processed_position"                                                    

PROMPT_TO_ALL_LLMs = """
"# Knowledge Graph Instructions for LLMs\n"
    "## 1. Overview\n"
    "You are a top-tier algorithm designed for extracting information in structured "
    "formats to build a knowledge graph.\n"
    "Try to capture as much information from the text as possible without "
    "sacrificing accuracy. Do not add any information that is not explicitly "
    "mentioned in the text.\n"
    "- **Nodes** represent entities and concepts.\n"
    "- The aim is to achieve simplicity and clarity in the knowledge graph, making it\n"
    "accessible for a vast audience.\n"
    "## 2. Labeling Nodes\n"
    "- **Consistency**: Ensure you use available types for node labels.\n"
    "Ensure you use basic or elementary types for node labels.\n"
    "- For example, when you identify an entity representing a person, "
    "always label it as **'person'**. Avoid using more specific terms "
    "like 'mathematician' or 'scientist'."
    "- **Node IDs**: Never utilize integers as node IDs. Node IDs should be "
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
    "## 4. Node Properties\n"
    "- Dates, URLs, Time, and Numerical Values: Instead of creating separate nodes for 
    these elements, represent them as properties of existing nodes."
    "- Example: Instead of creating a node labeled "2023-03-15" and connecting it to another node 
    with the relationship "BORN_ON", add a property called "born_on" to the person node with the 
    value "2023-03-15"."
    "## 5. Strict Compliance\n"
    "Adhere to the rules strictly. Non-compliance will result in termination."
    """
