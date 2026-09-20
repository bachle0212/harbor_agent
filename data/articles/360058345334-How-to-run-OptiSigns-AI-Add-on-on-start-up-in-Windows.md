# How to run OptiSigns AI Add-on on start up in Windows

Article URL: https://support.optisigns.com/hc/en-us/articles/360058345334-How-to-run-OptiSigns-AI-Add-on-on-start-up-in-Windows
Article ID: 360058345334
Updated: 2026-09-10T09:44:40Z

In Windows, you can use Windows' Task Scheduler to set up OptiSigns AI Add-on to run on start up.

It only take a few simple steps

Click **Start** -> Type "**Task Scheduler**" and open it

Then click **Create Basic task**

![image](https://support.optisigns.com/hc/article_attachments/360100967213)

Give it a name (e.g. OptiSigns AI Add-on Autostart)

Then click **Next**

![image](https://support.optisigns.com/hc/article_attachments/360098751914)

Next in Trigger section select "**When I Log on**"  
Please do not select other event like When computer start, it may not work.

![image](https://support.optisigns.com/hc/article_attachments/360100967293)

Next in Action section select "**Start a program**"

![image](https://support.optisigns.com/hc/article_attachments/360098752054)

Click Browse and browse to optisigns-ai-detection.exe that you've downloaded.

![image](https://support.optisigns.com/hc/article_attachments/360098752114)

Then click **Finish**

![image](https://support.optisigns.com/hc/article_attachments/360098752154)

That's all!

Next time your PC start up, it will start OptiSigns AI Detection app, doing it this way will also ensure that it will get started before the OptiSigns Digital Signage Player app start.
