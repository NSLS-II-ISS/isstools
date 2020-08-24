from isscloudtools.initialize import get_dropbox_service, get_slack_service
from isscloudtools.dropbox import *
from isscloudtools.slack import slack_upload_image
from xas.file_io import load_binned_df_from_file
from  isstools.elements.cloud_plotting import generate_output_figures
import os

class CloudDispatcher():
    def __init__(self, dropbox_service = None,slack_service = None):
        if dropbox_service==None:
            self.dropbox_service = get_dropbox_service()
        else:
            self.dropbox_service = dropbox_service
        if slack_service==None:
            self.slack_service, self.slack_client_oath = get_slack_service()
        else:
            self.slack_service = slack_service
        self.email = ''



    def set_contact_info(self,email):
        self.email = email

    def load_to_dropbox(self,path):
        df, header = load_binned_df_from_file(path)
        h = header.replace('#', '')
        h = h.replace('\n', ',')
        d = dict()
        for element in h.split(', '):
            if ':' in element:
                x = element.split(':')
                d[x[0]] = x[1]

        dn = '/{}/{}/{}/'.format(d['Year'], d['Cycle'], d['Proposal']).replace(' ', '')
        dropbox_upload_files(self.dropbox_service,path, dn, os.path.basename(path))

    def post_to_slack(self,path,slack_channel):
        image_path = os.path.splitext(path)[0]+'.png'
        print('image' + image_path)
        generate_output_figures(path,image_path)
        slack_upload_image(self.slack_service,
                           image_path,slack_channel,
                           os.path.basename(path).split('.')[0])










