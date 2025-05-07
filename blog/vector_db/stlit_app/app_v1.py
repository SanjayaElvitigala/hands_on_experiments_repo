import streamlit as st
import difflib
import numpy as np
import pandas as pd
import faiss
from sentence_transformers import SentenceTransformer


df = pd.read_csv("../sample_data.csv").drop(["Unnamed: 0"], axis=1)

# Step 2: Convert Descriptions to Vectors using a Pre-trained Model
model = SentenceTransformer("all-MiniLM-L6-v2")  # Fast & effective

# Generate embeddings
description_embeddings = model.encode(df["description"].tolist(), convert_to_numpy=True)

# Step 3: Normalize (optional but recommended for cosine similarity)
description_embeddings = description_embeddings / np.linalg.norm(
    description_embeddings, axis=1, keepdims=True
)

# Step 4: Create FAISS Index
dimension = description_embeddings.shape[1]
index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity

# Step 5: Add Vectors to Index
index.add(description_embeddings)

# Search input
query = st.text_input("Search for a item : ")


if query:

    query_vector = model.encode([query], convert_to_numpy=True)
    query_vector = query_vector / np.linalg.norm(query_vector, axis=1, keepdims=True)

    k = 5  # number of nearest neighbors
    distances, indices = index.search(query_vector, k)
    st.write("Closest matches:")
    for i, idx in enumerate(indices[0]):
        st.markdown(
            f"Rank {i+1}: ID={df.iloc[idx]['item_number']}, Description='{df.iloc[idx]['description']}', Similarity={distances[0][i]:.4f}"
        )

