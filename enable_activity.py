import os
from azure.identity import DefaultAzureCredential
import httpx

endpoint = "https://gayatri-foundry-we.services.ai.azure.com/api/projects/proj-default"
agent_name = "Sovereign-Suitability-Engine"

credential = DefaultAzureCredential()
token = credential.get_token("https://ai.azure.com/.default").token

with httpx.Client() as client:
    response = client.patch(
        f"{endpoint}/agents/{agent_name}?api-version=v1",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/merge-patch+json"
        },
        json={
            "agent_endpoint": {
                "protocol_configuration": {
                    "responses": {},
                    "activity": {}
                },
                "authorization_schemes": [
                    {"type": "Entra"}
                ]
            }
        }
    )
    print(f"Status: {response.status_code}")
    print(response.json())