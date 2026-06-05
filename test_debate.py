import asyncio  
import sys  
import traceback  
  
sys.path.insert(0, '.')  
  
try:  
    from research.debate import SequentialDebate  
    print('Import OK')  
except Exception as e:  
    traceback.print_exc()  
    print(f'Error: {e}')  
    sys.exit(1)  
  
async def test():  
    async def fake_llm(messages, tools=None):  
        return {'content': 'test response ' + str(len(messages))}  
  
    debate = SequentialDebate(llm_call=fake_llm)  
    print('Starting debate...')  
    result = await debate.debate('Lithium-air batteries will achieve 1000 Wh/kg by 2030')  
    print('Researcher:', result.researcher_view[:80])  
    print('Critic:', result.critic_view[:80])  
    print('Verdict:', result.verdict, result.confidence)  
  
asyncio.run(test()) 
