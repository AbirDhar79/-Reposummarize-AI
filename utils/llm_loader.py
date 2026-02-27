from crewai import LLM

def load_llm(hf_api_key, model_name="mistralai/Mistral-7B-Instruct-v0.2"):

    return LLM(
        model=f"huggingface/{model_name}",
        api_key=hf_api_key,
        temperature=0.7,
        max_tokens=3000  # safe output size
    )
