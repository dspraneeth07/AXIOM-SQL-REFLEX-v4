import numpy as np
import torch

from transformers import AutoTokenizer, AutoModel


class HFTextEmbedder:
    def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.eval()

    @torch.no_grad()
    def encode(self, texts, normalize_embeddings: bool = True):
        if isinstance(texts, str):
            texts = [texts]

        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            return_tensors="pt"
        )

        outputs = self.model(**inputs)
        embeddings = outputs.last_hidden_state.mean(dim=1)
        embeddings = embeddings.cpu().numpy()

        if normalize_embeddings:
            embeddings = embeddings / np.linalg.norm(
                embeddings, axis=1, keepdims=True
            )

        return embeddings
