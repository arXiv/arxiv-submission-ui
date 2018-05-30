"""
Controller for verify_user action.

Creates an event of type `core.events.event.VerifyContactInformation`
"""

from wtforms import Form, BooleanField
from wtforms.validators import DataRequired

# from arxiv-submission-core.events.event import VerifyContactInformation

"""
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
"""

def verify_user(data):
    pass
    

class VerifyUserForm(Form):
    verify_user = BooleanField('By checking this box, I verify that my user information is correct.', validators=[DataRequired(), ])
