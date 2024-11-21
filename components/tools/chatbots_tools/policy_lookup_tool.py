import re
import numpy as np
from langchain_core.tools import tool
import config as cfg
from azure.ai.inference import EmbeddingsClient
from azure.core.credentials import AzureKeyCredential
import requests
from components.tools.chatbots_tools.global_config import GlobalConfig

class VectorStoreRetriever:
    def __init__(self, docs: list, vectors: list, oai_client):
        self._arr = np.array(vectors)
        self._docs = docs
        self._client = oai_client

    @classmethod
    def from_docs(cls, docs, oai_client):
        embeddings = oai_client.embed(
            model=cfg.EMBEDDING_DEPLOYMENT_NAME,
            input=[doc["page_content"] for doc in docs],
        )
        vectors = [emb.embedding for emb in embeddings.data]
        return cls(docs, vectors, oai_client)

    def query(self, query: str, k: int = 5) -> list:
        embed = self._client.embed(
            model=cfg.EMBEDDING_DEPLOYMENT_NAME, input=[query]
        )
        scores = np.array(embed.data[0].embedding) @ self._arr.T
        top_k_idx = np.argpartition(scores, -k)[-k:]
        top_k_idx_sorted = top_k_idx[np.argsort(-scores[top_k_idx])]
        return [
            {**self._docs[idx], "similarity": scores[idx]} for idx in top_k_idx_sorted
        ]

class PolicyLookupTool:
    def __init__(self):
        # Initialize the Azure Embeddings Client
        self.client = EmbeddingsClient(
            endpoint=cfg.EMBEDDING_ENDPOINT_URL,
            credential=AzureKeyCredential(cfg.AZURE_OPENAI_API_KEY),
            api_version=cfg.EMBEDDING_API_VERSION,
        )

        # Fetch and process the FAQ document
        response = requests.get(
            "https://storage.googleapis.com/benchmarks-artifacts/travel-db/swiss_faq.md"
        )
        response.raise_for_status()
        faq_text = response.text
        docs = [{"page_content": txt} for txt in re.split(r"(?=\n##)", faq_text)]

        # Create a retriever instance
        GlobalConfig.set_global_retriever(VectorStoreRetriever.from_docs(docs, self.client))

    @tool
    def lookup_policy(query: str) -> str:
        """Consult the company policies to check whether certain options are permitted.
        Use this before making any flight changes or performing other 'write' events."""
        docs = GlobalConfig.get_global_retriever().query(query, k=2)
        return "\n\n".join([doc["page_content"] for doc in docs])

# from policy_lookup_tool import PolicyLookupTool

# # Instantiate the tool
# policy_tool = PolicyLookupTool()

# # Use the lookup_policy function
# result = policy_tool.lookup_policy("What is the policy on flight changes?")
# print(result)
