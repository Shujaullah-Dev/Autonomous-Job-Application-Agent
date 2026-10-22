import re

SKILL_CATALOG = {
    'Python': ['python'], 'C/C++': ['c/c++'], 'HTML/CSS': ['html/css'],
    'JavaScript': ['javascript'], 'TypeScript': ['typescript'],
    'FastAPI': ['fastapi'], 'Flask': ['flask'], 'Django': ['django'],
    'React': ['react', 'reactjs'], 'Node.js': ['node.js', 'nodejs'],
    'PostgreSQL': ['postgresql', 'postgres'], 'SQLite': ['sqlite'],
    'MySQL': ['mysql'], 'SQL': ['sql'], 'Docker': ['docker'],
    'Git': ['git'], 'GitHub': ['github'], 'AWS': ['aws'], 'Azure': ['azure'],
    'LangChain': ['langchain'], 'LangGraph': ['langgraph'],
    'Machine Learning': ['machine learning'], 'Deep Learning': ['deep learning'],
    'Data Analysis': ['data analysis'], 'REST API': ['rest api', 'rest apis', 'restful api'],
    'WebSocket': ['websocket', 'websockets'], 'PyTorch': ['pytorch'],
    'TensorFlow': ['tensorflow'], 'Hugging Face': ['hugging face'],
    'sentence-transformers': ['sentence-transformers'], 'T5': ['t5'],
    'RAG': ['rag'], 'OpenCV': ['opencv'], 'YOLO': ['yolo'],
    'Whisper': ['whisper'], 'NumPy': ['numpy'], 'ESA SNAP API': ['esa snap api'],
    'Google Colab': ['google colab'], 'Sentinel-1 SAR': ['sentinel-1 sar'],
    'Multiprocessing': ['multiprocessing'], 'Streamlit': ['streamlit'],
    'FAISS': ['faiss'], 'PyMuPDF': ['pymupdf'], 'Ollama': ['ollama'],
    'Random Forest': ['random forest'], 'Firebase': ['firebase'],
    'Firestore': ['firestore'], 'Qt': ['qt'], 'mpi4py': ['mpi4py'],
}


def extract_skills(text: str) -> list[str]:
    found = []
    for name, aliases in SKILL_CATALOG.items():
        if any(re.search(r'(?<![A-Za-z0-9])' + re.escape(alias) + r'(?![A-Za-z0-9])', text, re.I)
               for alias in aliases):
            found.append(name)
    return found
