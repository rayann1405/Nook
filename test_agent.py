import sys
from nook.agent import ReActAgent
from nook.tools import build_tools
from nook.config import load_config
from nook.ollama_client import OllamaClient

config = load_config()
client = OllamaClient(base_url=config.ollama.base_url, temperature=config.ollama.temperature)
try:
    model = client.detect_model()
    print("Detected model:", model)
    client.set_model(model)
except Exception as e:
    print("Ollama error:", e)
    sys.exit(1)

tools = build_tools(config.agent.default_cwd, config.agent.max_file_bytes)
agent = ReActAgent(client=client, tools=tools, max_iterations=config.ollama.max_iterations)
print("Sending test message...")
result = agent.run("Fais un test de la commande ls -l")
print("Error:", result.error)
print("Answer:", result.answer)
for step in result.steps:
    print(step.kind, step.content)
