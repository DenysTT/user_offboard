import pymsteams
import os

WEBHOOK_URL = os.environ.get('TEAMS_WEBHOOK_URL')

myTeamsMessage = pymsteams.connectorcard(WEBHOOK_URL)


def send_message(users):
    myTeamsMessage.title("Auto offboard daily report")
    myTeamsMessage.summary("..")

    for k, v in users.items():
        myMessageSection = pymsteams.cardsection()
        myMessageSection.title("User %s details" % k)
        myMessageSection.activityText("\n".join(["- %s" % x for x in v]))
        myTeamsMessage.addSection(myMessageSection)

    myTeamsMessage.send()


def send_error_message(error):
    myTeamsMessage.title("Auto offboard script error")
    myTeamsMessage.summary("..")
    myMessageSection = pymsteams.cardsection()
    myMessageSection.title("Error details")
    myMessageSection.activityText("%s" % error)
    myTeamsMessage.addSection(myMessageSection)
    myTeamsMessage.send()
