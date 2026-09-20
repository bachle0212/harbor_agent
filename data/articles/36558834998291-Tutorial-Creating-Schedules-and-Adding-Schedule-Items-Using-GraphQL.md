# Tutorial: Creating Schedules and Adding Schedule Items Using GraphQL

Article URL: https://support.optisigns.com/hc/en-us/articles/36558834998291-Tutorial-Creating-Schedules-and-Adding-Schedule-Items-Using-GraphQL
Article ID: 36558834998291
Updated: 2026-09-10T10:46:21Z

Using GraphQL, it’s possible to create a schedule on OptiSigns, then add items to it and assign values to them. We’ll cover each of these steps in turn.

**1. Creating a New Schedule**

To create a new schedule, we’ll need a specific Mutation:

```
mutation CreateSchedule($payload: ScheduleInput!, $teamId: String){saveSchedule (payload:$payload,teamId:$teamId){   _id,   accountId,   createdAt,   createdBy,   groupId,   lastTeamId,   lastUpdatedBy,   lastUpdatedDate,   name,   path,   tags,   teamId   }}
```

**Variables:**

```
{“payload”: {   “groupId”:   “Name”:   “Path”:   “Tags”:   “teamId”:   }}
```

![image](https://support.optisigns.com/hc/article_attachments/36558841524243)

This Mutation creates a brand new schedule, as you can see from the data to the right:

![image](https://support.optisigns.com/hc/article_attachments/36558841526675)

**2. Updating Schedules**

This same Mutation can be used to update the schedule itself. In order to update the schedule, you’ll need to input the “_id” value in the payload:

![image](https://support.optisigns.com/hc/article_attachments/36558841527955)

Doing this will update the existing schedule.

![image](https://support.optisigns.com/hc/article_attachments/36558841534483)

**3. Adding Assets or Playlists to the Schedule**

Now, we’ll want to add an item to the schedule. For that, we’ll need another Mutation:

```
mutation addScheduleItem($force:Boolean,$payload: AddScheduleItemInput!, $teamId: String!){  addScheduleItem(force:$force,payload:$payload,teamId:$teamId){         _id,       name,       assetId,             teamId,       playlistId,       repeatObject{         id,         repeat,         text,         type,         rrule       },       range{startDate,endDate},       documentDuration  }}
```

![image](https://support.optisigns.com/hc/article_attachments/36558841535507)

**Variables:**

```
{"force": false, "payload": {"scheduleId": "",            "assetId": "",            "playlistId":"",            "type": "",            "repeatObject": {              "rrule": ""            },             "range": {               "startDate": "",               "endDate": ""            }     }, "teamId": ""}
```

![image](https://support.optisigns.com/hc/article_attachments/36558834984339)

When the values are set up correctly, your data should display like this:

![image](https://support.optisigns.com/hc/article_attachments/36558834986643)

**4. Editing Schedule Items**

Once you’ve created a schedule and set an item on it, it’s possible to edit those items. This requires yet another Mutation:

```
mutation updateScheduleItem($force:Boolean,$payload: UpdateScheduleItemInput!, $scope: APPLY_SCHEDULE_ITEM_SCOPES!){  updateScheduleItem(force:$force,payload:$payload,scope:$scope){       _id,       name,       assetId,             teamId,       playlistId,       repeatObject{         id,         repeat,         text,         type,         rrule       },       range{startDate,endDate},       documentDuration  }}
```

![image](https://support.optisigns.com/hc/article_attachments/36558834989843)

With this mutation, we’ll input these variables:

```
{"force": false, "payload": {"_id": "",            "assetId": "",            "playlistId":"",            "repeatObject": {              "rrule": ""             },            "range": {              "startDate": "",              "endDate": ""            } }, "scope": ""}
```

![image](https://support.optisigns.com/hc/article_attachments/36558834991379)

Here, we’ve changed the repeat frequency from daily to weekly, and the start date from December 18, 2024 to December 20, 2024. This is reflected in the data retrieved:

![image](https://support.optisigns.com/hc/article_attachments/36558841549075)

**Previous Article - [Tutorial: Creating or Updating Website Assets Using GraphQL](https://support.optisigns.com/hc/en-us/articles/36562094987795-Tutorial-Creating-or-Updating-Website-Assets-Using-GraphQL)**

**Next Article - [Pagination](https://support.optisigns.com/hc/en-us/articles/4414558369811-Pagination)**
