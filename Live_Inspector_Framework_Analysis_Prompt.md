You are analyzing a codebase I have open here. Do NOT write code, do NOT build anything, do NOT change any files. Your only job is to give me a complete, accurate summary of the framework in ONE single response, so I can hand that summary to another AI to design a new tool on top of it.

CONTEXT - WHY I NEED THIS:
I want to build a tool called Live Inspector. It must work like this, with no debug mode and no breakpoint:
- I run my existing test project normally
- As each code line runs, it should show live, on the right side of that line, what locator value it actually fetched (for example, an xpath that returns 11 elements, and after my Java code removes 0th and 11th, the clean filtered 9 elements)
- At the end of the test, the browser should NOT close, it should stay open in running mode until I manually close it
- Local development only, not CI
- It must work for Selenium, and ideally also Playwright

To design that tool, the other AI needs complete knowledge of my framework. That framework is called CTS. It is a parent framework, and my Salesforce test project is a child project that uses CTS for driver and everything else.

YOUR TASK - ANALYZE BOTH REPOS IF YOU HAVE THEM:
1. The CTS parent framework repo
2. My child test project repo (Salesforce project)

If you only have one repo open, analyze that one fully and clearly say which parts of the other repo you could NOT see.

OUTPUT - GIVE ME ALL OF THIS IN ONE RESPONSE, DO NOT SPLIT IT, DO NOT ASK FOLLOW-UP QUESTIONS, DO NOT SAY "CONTINUED IN NEXT MESSAGE":

1. Framework overview
- What is CTS, what modules/packages does it have, what is the folder structure
- How does a child project depend on CTS (Maven pom dependency, version, parent pom or jar?)
- What Java version, Selenium version, TestNG / Cucumber version, Maven setup

2. Driver creation - THIS IS THE MOST IMPORTANT PART
- Exact file path, class name, and method name that creates the WebDriver
- Is it a Factory class, a BaseTest class, a singleton, or something else?
- Is the driver stored in ThreadLocal? How is parallel execution handled?
- What browser options are set (ChromeOptions, headless or not, etc.)
- How does a child test actually get the driver? Example: extends BaseTest, or calls CTS.getDriver(), or injects it - give the exact call a child test uses
- Paste only the driver creation method signature and the key lines, not the whole file

3. Driver lifecycle and teardown
- Where and when is driver.quit() or driver.close() called? Exact class and method
- What happens in @BeforeMethod / @BeforeSuite / @AfterMethod / @AfterSuite, or Cucumber @Before / @After hooks
- Who owns teardown, CTS or the child project?

4. How tests are written in the child project
- TestNG or Cucumber? If Cucumber, how does a feature file connect to a step definition, and how does a step definition connect to a page class?
- Give one real example chain: feature step -> step definition file and method -> page class file and method -> driver.findElement line
- How are locators defined in page classes (By fields, methods, properties file?)
- How are waits handled (explicit wait class, base page methods?)

5. Configuration
- Where are config files (properties, yaml, xml), what keys exist for browser, environment, URL, timeouts
- Do NOT include any passwords, tokens, secrets, or full internal URLs with credentials. Only list the config keys and file names.

6. Listeners, hooks, reporting
- Any existing TestNG listeners, Cucumber plugins, or CTS listeners already registered, and what they do
- How is reporting done, if any

7. Best integration point for Live Inspector
- Based ONLY on what you found in the code, where is the single best place to wrap/intercept the driver so ALL child projects get it, with the smallest change? Name the exact class and method.
- What would break if we wrap the driver there? What classes directly use the raw driver instead of going through CTS?

8. Anything missing or unclear
- If any piece above is NOT FOUND in the code, write "NOT FOUND" for that piece. Do not guess, do not invent class names, method names, or file paths. Only report what is actually in the code you can see.

RULES:
- Be precise with file paths, class names, and method names, copied exactly from the code.
- Keep code snippets very short, only where they prove how driver is created or how a child gets it.
- No secrets, no passwords, no tokens.
- One complete response only, covering all 8 sections above.
