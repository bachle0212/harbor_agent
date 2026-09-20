# Generate & Manage an OptiSigns API Key

Article URL: https://support.optisigns.com/hc/en-us/articles/4414563797139-Generate-Manage-an-OptiSigns-API-Key
Article ID: 4414563797139
Updated: 2026-09-10T09:47:50Z

In order to use the API, you will need first get an API key. To get an API key, you can either use the link below, or click the **API Keys** button in the side menu of account management on the OptiSigns portal.

|  |
| --- |
| **NOTE** |
| In order to generate an API Key, you must:   - Be on the OptiSigns [**Pro Plus plan or above**](https://www.optisigns.com/pricing) - Be the **Account Owner** or **Super Admin** - Not be using a white-labeled portal |

To get an Within OptiSigns, click the profile menu on the top right, go to **More**, then **API Keys**.

Or, click this link: <https://app.optisigns.com/app/s/apikeys>

### ![OptiSigns profile menu with More expanded, showing API Keys in the submenu](https://support.optisigns.com/hc/article_attachments/55264237024403)

### Create API Key

1. Click the **New API Key** button  

![New API Key button at the top right of the API Keys page](https://support.optisigns.com/hc/article_attachments/55264244280595)

2. Enter the API Key name, and select the scopes and permissions for the API key.  

![API Key dialog: Name field and Scopes toggles for Screens, Files/Assets, Playlists, Schedules](https://support.optisigns.com/hc/article_attachments/55264244282899)

3. Save the API key safely, the key will be used to access your account via API. It can be re-displayed at any time from the row's three-dot menu and selecting Reveal.

![API Token dialog showing the generated token (blurred) with a Copy button](https://support.optisigns.com/hc/article_attachments/55264244283795)

Click **Copy** to quickly get the key and Paste it where it needs to go.

### Use API Key

To use the API key, put it in the HTTP request header following this format.

Authorization: Bearer YOUR_KEY_HERE

In the OptiSigns GraphQL playground, you will be able to query your data if the API key is successfully added.

![GraphQL playground HTTP HEADERS pane with an Authorization Bearer token](https://support.optisigns.com/hc/article_attachments/37490069240083)

**Previous Article -** [**Introduction**](https://support.optisigns.com/hc/en-us/articles/4414552808467-Introduction)

**Next Article -** [**Get Started**](https://support.optisigns.com/hc/en-us/articles/4414563863827-Get-Started)
