# Zenith-OS Test Queries

Test queries for each feature area. Copy-paste into the Zenith chat to test.

---

## Basic Chat
```
Hello, what can you do?
```
```
What time is it?
```
```
Tell me a fun fact about space.
```

---

## Research Lab
```
Research the latest developments in quantum computing.
```
```
Find information about climate change solutions and summarize the top 3 approaches.
```
```
Research how to start a SaaS business in 2026.
```

---

## Document Processing
```
Read the Excel file at C:\Users\mjtan\Desktop\sales_data.xlsx and summarize the data.
```
```
Create an Excel spreadsheet with 5 rows of sample sales data.
```
```
Parse the PDF at C:\Users\mjtan\Desktop\report.pdf and extract key findings.
```
```
Convert the CSV file data.csv to an Excel file.
```

---

## Dynamic Workflows
```
Create a workflow: install dependencies, build project, run tests. If tests fail, skip and deploy anyway.
```
```
Save a workflow called "deploy-app" that builds, tests, and deploys to Vercel.
```
```
Run a workflow with an approval gate before deploying to production.
```
```
Execute a parallel workflow: research React, Vue, and Svelte at the same time, then compare results.
```

---

## Swarm Multi-Agent
```
Use a swarm of agents to research React vs Vue vs Svelte, compare them, and give me a recommendation.
```
```
Spawn 3 workers to analyze the codebase for bugs, performance issues, and security vulnerabilities in parallel.
```
```
Use a leader-worker swarm to break down "build a todo app" into subtasks and execute them.
```

---

## Browser Automation
```
Open Chrome and navigate to github.com.
```
```
Open Firefox and search for "Python async patterns" on Google.
```
```
Detect all installed browsers on my system.
```
```
Create a new browser session in Edge and navigate to github.com.
```
```
Read the current page content from the browser.
```
```
Click the sign-in button on the current page.
```

---

## PC Automation
```
Copy "Hello World" to clipboard.
```
```
What's on my clipboard right now?
```
```
List all my monitors.
```
```
Take a screenshot of monitor 2.
```
```
Snap the current window to the left side.
```
```
Show me all running Chrome processes.
```
```
Kill the process named notepad.exe.
```
```
Open my Downloads folder in Explorer.
```
```
Show a notification saying "Build completed successfully".
```
```
Read the text on my screen using OCR.
```

---

## Self-Diagnosis & Self-Improvement

### Health Checks
```
Run a full system diagnostic.
```
```
Check my system health score.
```
```
What issues do I have with my Zenith setup?
```
```
Are all my dependencies installed correctly?
```
```
Is my embedding model loaded and working?
```
```
How much disk space does Zenith use?
```

### Token Efficiency
```
Analyze my token usage for the past week.
```
```
Am I wasting tokens on repeated queries?
```
```
What's my average token efficiency score?
```
```
Which of my recent messages used the most tokens?
```
```
How can I reduce my token consumption?
```

### Error Analysis
```
What errors have occurred recently?
```
```
What's my error rate this week?
```
```
Are there any patterns in my failed requests?
```
```
Which tools are failing the most?
```

### Memory Health
```
Check my memory system health.
```
```
How large is my memory storage?
```
```
Is my soft memory working correctly?
```
```
Clean up old memory logs.
```

### Auto-Fix
```
Auto-fix any detected problems.
```
```
Install missing dependencies.
```
```
Clean up old logs and free disk space.
```
```
Fix all fixable issues automatically.
```

### Self-Improvement
```
How can I improve my responses?
```
```
What were my worst-performing messages?
```
```
Show me my performance trends over time.
```
```
What categories do I struggle with most?
```
```
Give me suggestions to be more efficient.
```

### Performance Scoring
```
Score my last response.
```
```
What grade did I get on my last message?
```
```
How efficient was my last tool usage?
```
```
Am I getting better over time?
```

### Config & Setup
```
Is my .env file configured correctly?
```
```
Do I have all required API keys set up?
```
```
What LLM provider am I using?
```
```
Check if the browse CLI is installed.
```
```
Verify my Telegram bot configuration.
```

---

## Combined / Advanced
```
Use a swarm to research the top 5 AI frameworks, then save the results to an Excel file.
```
```
Open Chrome, navigate to my bank website, take a screenshot, then copy the account balance to clipboard.
```
```
Create a workflow: spawn 3 agents to analyze code in parallel, collect results, then show a notification when done.
```
```
Research "AI company management tools", write findings to a document, then open it in the browser.
```

---

## Polsia Integration (if available)
```
Research Polsia AI and how it helps create and manage companies.
```
```
What are the key features of Polsia for business automation?
```
```
How does Polsia compare to traditional company management tools?
```

---

## Telegram Bot

### Setup
1. Message @BotFather on Telegram
2. Send /newbot and follow instructions
3. Copy the bot token
4. Add to `.env` file: `TELEGRAM_BOT_TOKEN=your_token_here`
5. Run: `launch.bat` → choose option [2] Telegram Bot

### Test Commands (send to your bot)
```
/start
```
```
/help
```
```
Hello, what can you do?
```
```
Research the latest AI news.
```
```
What is the weather in Tokyo?
```
```
Create a todo list for building a web app.
```
```
/clear
```
```
/status
```
