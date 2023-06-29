import os
import re

from dotenv import load_dotenv
from langchain.chains import ConversationalRetrievalChain, LLMChain
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain.chat_models import ChatOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain.vectorstores import Milvus


class QueryHandler:
    def __init__(self, openai_api_key, milvus_api_key):
        load_dotenv()  # take environment variables from .env.
        self.openai_api_key = openai_api_key
        self.milvus_api_key = milvus_api_key

        connection_args = {
            "uri": "https://in03-5052868020ac71b.api.gcp-us-west1.zillizcloud.com",
            "user": "vaclav@pechtor.ch",
            "token": milvus_api_key,
            "secure": True,
        }

        os.environ["OPENAI_API_KEY"] = self.openai_api_key
        self.embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
        self.milvus = Milvus(
            embedding_function=self.embeddings,
            collection_name="LuGPT",
            connection_args=connection_args,
        )
        self.chat_history = []

        prompt_template="""Angesichts der folgenden Konversation und einer anschließenden Frage, formulieren Sie die Nachfrage so um, dass sie als eigenständige Frage gestellt werden kann.
        Alle Ausgaben müssen in Deutsch sein.
        Wenn Sie die Antwort nicht kennen, sagen Sie einfach, dass Sie es nicht wissen, versuchen Sie nicht, eine Antwort zu erfinden.

        Chatverlauf:
        {chat_history}
        Nachfrage: {question}
        Eigenständige Frage:

        """

        PROMPT = PromptTemplate(
            template=prompt_template, input_variables=["chat_history", "question"]
        )

        
        llm = ChatOpenAI(temperature=0, model_name='gpt-3.5-turbo-16k-0613')
        question_generator = LLMChain(llm=llm,
                                    prompt=PROMPT,
                                    )
        doc_chain = load_qa_with_sources_chain(llm, chain_type="map_reduce")

        self.chain = ConversationalRetrievalChain(
            retriever=self.milvus.as_retriever(),
            question_generator=question_generator,
            combine_docs_chain=doc_chain,
        )

    def process_output(self, output):
        # Split the answer into the main text and the sources
        answer, raw_sources = output['answer'].split('SOURCES:\n', 1)

        # Split the raw sources into a list of sources
        raw_sources_list = raw_sources.split('- ')

        # Process each source to turn it back into a valid URL
        sources = []
        for raw_source in raw_sources_list:
            if raw_source:  # Ignore empty strings
                # Remove the ending '.txt' and replace '__' with '/'
                valid_url = 'https://' + raw_source.replace('__', '/').rstrip('.txt\n')
                sources.append(valid_url)

        return answer, sources

    def get_answer(self, query):

        result = self.chain({"question": query, "chat_history": self.chat_history})
        self.chat_history.append((query, result["answer"]))
        return result