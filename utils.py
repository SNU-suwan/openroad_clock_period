import os

def create_backups(file_dir):

    file_name = file_dir.split('.')[0]
    file_extension = file_dir.split('.')[1]

    backup_idx = 0
    backup_file_dir = file_name + f'_backup{backup_idx}.' + file_extension
    while os.path.isfile(backup_file_dir):
        backup_idx += 1
        backup_file_dir = file_name + f'_backup{backup_idx}.' + file_extension
     
    os.system(f'cp {file_dir} {backup_file_dir}')
