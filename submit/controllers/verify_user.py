"""
Controller for verify_user action.

Creates an event of type `core.events.event.VerifyContactInformation`
"""

from typing import Tuple, Dict, Any, Optional

from wtforms import Form, BooleanField
from wtforms.validators import DataRequired

from arxiv import status

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

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]

def verify_user(request_params: dict) -> Response:
    form = VerifyUserForm()

    response_data = dict()
    response_data['form'] = form

    return response_data, status.HTTP_200_OK, {}

    

class VerifyUserForm(Form):
    verify_user = BooleanField('By checking this box, I verify that my user information is correct.', validators=[DataRequired(), ])
