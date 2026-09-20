# Set OptiSigns as ScreenSaver on Windows

Article URL: https://support.optisigns.com/hc/en-us/articles/360053211594-Set-OptiSigns-as-ScreenSaver-on-Windows
Article ID: 360053211594
Updated: 2026-09-10T09:43:48Z

Sometimes, you would want to set OptiSigns to run if the PC is idle for some time.  
This is a good use case for Kiosk and Public use computers.

In this guide, we will walk you through end to end process to set OptiSigns app as Screen Saver on Windows.

### How to Set OptiSigns as Screen Saver on Windows.

First open OptiSigns side menu, click Advanced, and turn on "Screen Saver Mode".

When this mode is on, OptiSigns will be closed on any mouse move, click, or keyboard pressed.

![image](https://support.optisigns.com/hc/article_attachments/4403429024787)

Then use Window's task scheduler to run OptiSigns when the PC is idle.

Here's the steps, on Windows click Start, search for "Task Scheduler" & open it.

Task Scheduler -> Create Task -> "Trigger" tab -> New -> "Begin the task:" -> "On Idle"

Next, go to the "Actions" tab and set the action to whatever it is you want to run.

- Search for "**Task Scheduler**" & open it

![image](https://support.optisigns.com/hc/article_attachments/360091166373)

- **Create Task** in your Task Scheduler

![image](https://support.optisigns.com/hc/article_attachments/360091166393)

- Set **Configure** for your device

![image](https://support.optisigns.com/hc/article_attachments/360091166413)

- Go to **Triggers** tap, and click "**New ...**"

![image](https://support.optisigns.com/hc/article_attachments/360091166433)

- Set Begin the task: "**On idle**"

![image](https://support.optisigns.com/hc/article_attachments/360091166453)

- Go to **Actions** tap, and click "**New ...**"

![image](https://support.optisigns.com/hc/article_attachments/360091166473)

- Set Action: "**Start a program**", and "**Browse**" OptiSigns app's location.

![image](https://support.optisigns.com/hc/article_attachments/360089015334)

- Go to **Condition** tap, and set the condition for your computer.

![image](https://support.optisigns.com/hc/article_attachments/360089015354)

- Go to **Setting** tap, and set "**Run a new instance in parallel**" (The Task Scheduler service will run the new instance of the task in parallel with the instance that is already running.)

![image](https://support.optisigns.com/hc/article_attachments/360089015394)

- After that, you finish your task setting. You can click "**Run**" to start this task.

![image](https://support.optisigns.com/hc/article_attachments/360089015494)

- Your status of task will show "**Running**".

![image](https://support.optisigns.com/hc/article_attachments/360091166533)

- Close OptisSigns app

Once the computer is idle, your screen will run OptiSigns app.

You're ready to go.

**IMPORTANT:**

Because OptiSigns is closed on any mouse move, click or key press when Screen Saver mode is turned on.

If you want to control OptiSigns again, press Ctrl + Alt + A or Ctrl + Alt + S, this will turn off Screen Saver mode, and you can interact with OptiSigns.

If you have feedback on how to make the how-to guides better, please let us know at: [support@optisigns.com](mailto:support@optisigns.com)
