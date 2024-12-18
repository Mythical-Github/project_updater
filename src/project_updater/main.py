import os
import sys
import shutil
from pathlib import Path
from zipfile import ZipFile

import requests

from project_updater.log_py import log_message


if getattr(sys, 'frozen', False):
    SCRIPT_DIR = Path(sys.executable).parent
else:
    SCRIPT_DIR = Path(__file__).resolve().parent


def delete_empty_dirs(proj_dir: str):
    log_message(f"Starting to delete empty directories in {proj_dir}")
    try:
        for dirpath, dirnames, filenames in os.walk(proj_dir, topdown=False):
            if not os.listdir(dirpath):
                os.rmdir(dirpath)
                log_message(f"Deleted empty directory: {dirpath}")
        log_message(f"Completed deletion of empty directories in {proj_dir}")
    except Exception as e:
        log_message(f"Error occurred while deleting directories in {proj_dir}. Error: {e}")


def get_recursive_backup_name(path):
    backup_path = f"{path}.bak"
    if os.path.exists(backup_path):
        return get_recursive_backup_name(backup_path)
    return backup_path


def create_recursive_backup(original_dir: str) -> str:
    if os.path.isdir(original_dir):
        backup_path = get_recursive_backup_name(original_dir)
        os.makedirs(backup_path)
    return backup_path


def download_file(url, dest_dir=SCRIPT_DIR):
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = sys.stdout

    local_filename = os.path.join(dest_dir, url.split('/')[-1])
    log_message(f"Starting download from {url} to {local_filename}")
    
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        log_message(f"Successfully downloaded {url} to {local_filename}")
    except Exception as e:
        log_message(f"Failed to download {url}. Error: {e}")
    
    sys.stdout = original_stdout
    sys.stderr = original_stderr
    
    return local_filename


def unzip_release(zip_path, dest_folder=SCRIPT_DIR):
    log_message(f"Starting extraction of {zip_path} to {dest_folder}")
    try:
        with ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(dest_folder)
        log_message(f"Successfully extracted {zip_path} to {dest_folder}")
    except Exception as e:
        log_message(f"Failed to extract {zip_path}. Error: {e}")


def clean_temp_dir(temp_dir_path: str):
    if os.path.isdir(temp_dir_path):
        log_message(f"Directory exists: {temp_dir_path}. Proceeding to delete.")
        try:
            shutil.rmtree(temp_dir_path)
            log_message(f"Successfully deleted the temporary directory: {temp_dir_path}")
        except Exception as e:
            log_message(f"Failed to delete the temporary directory: {temp_dir_path}. Error: {e}")
    else:
        log_message(f"Directory not found: {temp_dir_path}. No deletion needed.")


def download_content(proj_temp_dir: str, content_zip_urls: list):
    log_message(f"Creating temporary directory: {proj_temp_dir} for content download")
    try:
        os.makedirs(proj_temp_dir, exist_ok=True)
        log_message(f"Successfully created or confirmed existence of directory: {proj_temp_dir}")
    except Exception as e:
        log_message(f"Failed to create directory {proj_temp_dir}. Error: {e}")
        return
    
    for content_zip_url in content_zip_urls:
        log_message(f"Starting download for content: {content_zip_url}")
        try:
            download_file(content_zip_url, proj_temp_dir)
            log_message(f"Successfully downloaded content from {content_zip_url}")
        except Exception as e:
            log_message(f"Failed to download content from {content_zip_url}. Error: {e}")


def unzip_content_zips(proj_temp_dir: str):
    log_message(f"Starting to unzip content in {proj_temp_dir}")
    files = [f for f in os.listdir(proj_temp_dir) if os.path.isfile(os.path.join(proj_temp_dir, f))]
    
    for file in files:
        file_path = os.path.join(proj_temp_dir, file)
        log_message(f"Unzipping file: {file_path}")
        try:
            unzip_release(file_path, proj_temp_dir)
            log_message(f"Successfully unzipped {file_path}")
            os.remove(file_path)
            log_message(f"Removed zip file after extraction: {file_path}")
        except Exception as e:
            log_message(f"Failed to unzip {file_path}. Error: {e}")
    
    log_message(f"Completed unzipping all content in {proj_temp_dir}")


def get_files_and_dirs_in_dir_tree(dir_tree: str) -> list:
    all_files_and_dirs = []
    root_dir = Path(dir_tree)

    for item in root_dir.rglob('*'):
        all_files_and_dirs.append(item)

    return all_files_and_dirs


def backup_backups(backup_dir):
    if os.path.isdir(backup_dir):
        new_backup_dir = create_recursive_backup(backup_dir)
        shutil.move(backup_dir, new_backup_dir)
    os.makedirs(backup_dir)


def backup_dir_tree(
        proj_dir: str,
        backup_dir_tree: bool = True, 
        backup_exclusions: list = []
    ):
    log_message(f"Starting backup of directory tree for {proj_dir}")
    
    if backup_dir_tree:
        backup_dir = os.path.join(proj_dir, 'backup')
        log_message(f"Backing up directory to {backup_dir}")
        backup_backups(backup_dir)
        
        before_file_set = [os.path.normpath(exclusion) for exclusion in get_files_and_dirs_in_dir_tree(proj_dir)]
        backup_exclusions = [os.path.normpath(exclusion) for exclusion in backup_exclusions]
        
        dir_list = []
        file_list = []
        for backup_exclusion in backup_exclusions:
            path = os.path.join(proj_dir, backup_exclusion)
            if os.path.isfile(path):
                file_list.append(backup_exclusion)
            if os.path.isdir(path):
                dir_list.append(backup_exclusion)
        
        path_suffixes = [os.path.relpath(before_file, proj_dir) for before_file in before_file_set]
        path_suffixes = [
            item for item in path_suffixes 
            if not any(item.startswith(entry) for entry in dir_list) 
            and item not in file_list
        ]
        
        for path_suffix in path_suffixes:
            full_before_path = os.path.join(proj_dir, path_suffix)
            full_after_path = os.path.join(backup_dir, path_suffix)
            file_dir = os.path.dirname(full_after_path)

            try:
                if os.path.isfile(full_before_path):
                    os.makedirs(file_dir, exist_ok=True)
                    shutil.move(full_before_path, full_after_path)
                    log_message(f"Backed up file: {full_before_path} to {full_after_path}")
                elif os.path.isdir(full_before_path):
                    os.makedirs(full_after_path, exist_ok=True)
                    log_message(f"Backed up directory: {full_before_path} to {full_after_path}")
            except Exception as e:
                log_message(f"Error backing up {full_before_path}. Error: {e}")
        
        log_message(f"Backup completed for {proj_dir}")


def delete_dir_tree(
        proj_dir: str, 
        delete_dir_tree: bool = False, 
        delete_exclusions: list = []
    ):
    log_message(f"Starting to delete directory tree for {proj_dir}")
    
    if delete_dir_tree:
        delete_exclusions.append('backup')
        delete_exclusions = [os.path.normpath(exclusion) for exclusion in delete_exclusions]
        
        proj_dir_files = [os.path.normpath(path) for path in get_files_and_dirs_in_dir_tree(proj_dir)]
        proj_dir_files_relative_paths = [os.path.relpath(path, proj_dir) for path in proj_dir_files]

        files_to_delete = []
        for file in proj_dir_files_relative_paths:
            should_exclude = any(file.startswith(exclusion) for exclusion in delete_exclusions)
            if not should_exclude:
                files_to_delete.append(file)

        for relative_path in files_to_delete:
            file_path = os.path.join(proj_dir, relative_path)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    log_message(f"Deleted file: {file_path}")
                elif os.path.isdir(file_path):
                    if not os.listdir(file_path):
                        shutil.rmtree(file_path)
                        log_message(f"Deleted empty directory: {file_path}")
            except Exception as e:
                log_message(f"Error deleting {file_path}. Error: {e}")
        
        log_message(f"Directory tree deletion completed for {proj_dir}")



def move_content(
        proj_temp_dir: str, 
        proj_dir: str,
        overwrite_files: bool, 
        overwrite_files_exclusions: list = []
    ):
    log_message(f"Starting to move content from {proj_temp_dir} to {proj_dir}")
    
    overwrite_exclusions = [os.path.normpath(exclusion) for exclusion in overwrite_files_exclusions]
    before_file_set = [os.path.normpath(exclusion) for exclusion in get_files_and_dirs_in_dir_tree(proj_temp_dir)]
    before_file_set_relative_paths = [os.path.relpath(before_file, proj_temp_dir) for before_file in before_file_set]

    for partial_path in before_file_set_relative_paths:
        full_before_path = os.path.join(proj_temp_dir, partial_path)
        full_after_path = os.path.join(proj_dir, partial_path)
        try:
            if os.path.isfile(full_before_path):
                file_dir = os.path.dirname(full_after_path)
                os.makedirs(file_dir, exist_ok=True)
                if overwrite_files:
                    if os.path.isfile(full_after_path):
                        if partial_path not in overwrite_exclusions:
                            os.remove(full_after_path)
                            os.makedirs(file_dir, exist_ok=True)
                            shutil.move(full_before_path, full_after_path)
                            log_message(f"Overwritten file: {full_before_path} to {full_after_path}")
                    else:
                        shutil.move(full_before_path, full_after_path)
                        log_message(f"Moved file: {full_before_path} to {full_after_path}")
                else:
                    if not os.path.isfile(full_after_path):
                        shutil.move(full_before_path, full_after_path)
                        log_message(f"Moved file: {full_before_path} to {full_after_path}")
            else:
                shutil.move(full_before_path, full_after_path)
                log_message(f"Moved directory: {full_before_path} to {full_after_path}")
        except Exception as e:
            log_message(f"Error moving {full_before_path} to {full_after_path}. Error: {e}")
    
    log_message(f"Content move completed from {proj_temp_dir} to {proj_dir}")



def update_project(
    project_directory,
    content_zip_urls,
    backup_directory_tree=True,
    backup_exclusions=[],
    delete_directory_tree=True,
    delete_exclusions=[],
    overwrite_files=True,
    overwrite_exclusions=[]
):
    if backup_directory_tree == None:
        backup_directory_tree = True
        
    if backup_exclusions is None:
        backup_exclusions = []

    if delete_directory_tree == None:
        delete_directory_tree = False

    if delete_exclusions is None:
        delete_exclusions = []

    if overwrite_files == None:
        overwrite_files == True
        
    if overwrite_exclusions is None:
        overwrite_exclusions = []
    
    """
    Updates a project by downloading and managing content as specified.

    Args:
        project_directory (str): Path of the directory of the project to update.
        repo_release_urls (str): A list of URLs of content to download and unzip to the specified project directory.
        backup_directory_tree (bool, optional): Whether to back up the project directory's content before installing new content.
        backup_exclusions (list, optional): List of file names and/or directories, relative to the project directory, to exclude from backup.
        delete_directory_tree (bool, optional): Whether to delete the project directory's content before installing new content.
        delete_exclusions (list, optional): List of file names and/or directories, relative to the project directory, to exclude from deletion.
        overwrite_files (bool, optional): Whether to overwrite existing files when installing new content.
        overwrite_exclusions (list, optional): List of file names and/or directories, relative to the project directory, to exclude from being overwritten.

    Returns:
        None
    """

    proj_dir = project_directory
    proj_temp_dir = os.path.join(proj_dir, 'temp')
    os.makedirs(proj_temp_dir, exist_ok=True)

    clean_temp_dir(proj_temp_dir)
    backup_dir_tree(proj_dir, backup_directory_tree, backup_exclusions)
    delete_dir_tree(proj_dir, delete_directory_tree, delete_exclusions)
    download_content(proj_temp_dir, content_zip_urls)
    unzip_content_zips(proj_temp_dir)
    move_content(proj_temp_dir, proj_dir, overwrite_files, overwrite_exclusions)
    clean_temp_dir(proj_temp_dir)
    delete_empty_dirs(proj_dir)
