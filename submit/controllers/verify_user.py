""" 
Controller for verify_user action. 

Creates an event of type `core.events.event.VerifyContactInformation`
"""

from wtforms import Form

from core.events.event import VerifyContactInformation

def verify_user(data):
    if method == 'GET':
        # generate new wtform
        pass
    elif method == 'POST':
        # instantiate new form with POST data
        # is form valid?
        if form.validate():
            # create event
            # generate redirect to next step
            pass

class VerifyUserForm(Form):
    pass
