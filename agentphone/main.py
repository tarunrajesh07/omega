import argparse
import os

from agentphone import AgentPhone
from dotenv import load_dotenv

load_dotenv()

client = AgentPhone(api_key=os.environ["AGENTPHONE_API_KEY"])


def smoke_test():
    agents = client.agents.list()
    print(f"Auth OK. {agents.total} existing agent(s).")
    for a in agents.data:
        print(f"  - {a.id}  {a.name}")


def provision():
    agent = client.agents.create(name="Omega Agent")
    number = client.numbers.buy(country="US", agent_id=agent.id)
    print(f"Agent {agent.id} live on {number.phone_number}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--provision", action="store_true",
                        help="Create an agent and buy a phone number (costs money)")
    args = parser.parse_args()

    if args.provision:
        provision()
    else:
        smoke_test()
