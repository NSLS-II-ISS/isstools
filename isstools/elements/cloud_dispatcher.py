from isscloudtools.initialize import get_dropbox_service
from xas.file_io import load_binned_df_from_file
import os

class CloudDispatcher():
    def __init__(self,):
        self.dropbox_service = get_dropbox_service()
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
        fn = '{}{}'.format(dn, os.path.basename(path))
        with open(path, "rb") as f:
            file_id = self.dropbox_service.files_upload(f.read(), fn)






