# Copyright 2020 Webitects Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from minio import Minio
from minio.error import (ResponseError, BucketAlreadyOwnedByYou, BucketAlreadyExists)
import argparse
import sys
import getopt
import urllib
import logging
import shutil
import pymongo
from os import path, listdir, makedirs, devnull
import subprocess
import os
import datetime
from shlex import split as command_to_array
from subprocess import CalledProcessError, check_call

slash_type = '\\' if os.name == 'nt' else '/'
class MongoBackup:
    def __init__(self, host, user, password, port, access_key, secret_key,  connection_string, database_name, endpoint, bucket, location) -> None:
        self.host = host
        self.password = password
        self.port = port
        self.user = user
        self.connection_string = connection_string
        
        self.secret_key = secret_key
        self.access_key = access_key
        self.client = pymongo.MongoClient(connection_string)
        self.database = self.client[str(database_name).strip()]
        self.collections = self.database.list_collection_names()  
        self.minio_bucket = bucket
        self.database_name = str(database_name).strip()
        self.minio_endpoint = endpoint
        self.location = location
    # End __init__()
    
    def backup_to_minio(self):
        print("Uploading zip file...")
        minioClient = Minio(self.minio_endpoint.strip(),
                    access_key=self.access_key.strip(),
                    secret_key=self.secret_key.strip(),
                    secure=True)
        try:
            minioClient.make_bucket(self.minio_bucket, location=self.location)
        except BucketAlreadyOwnedByYou as err:
            pass
        except BucketAlreadyExists as err:
            pass
        except ResponseError as err:
            raise

        try:
            minioClient.fput_object(self.minio_bucket, self.zip_name, self.zip_name)
        except ResponseError as err:
            print(err)
        print("Uploaded zip")
        print("Backup process complete. Have a nice day :)")
    # End backup_to_minio()

    def create_folder(self) -> None:
        d = datetime.datetime.now().strftime('%m:%d:%Y')
        path = os.getcwd()
        path = path + slash_type + d + "_backup"
        self.backup_folder_path = path
        try:
            os.mkdir(self.backup_folder_path)
        except Exception:
            pass
    # End create_folder()

    def backup_mongodump(self) -> None:
        today = datetime.datetime.now()
        self.create_folder()
        output_dir = os.path.abspath(os.path.join(
            os.path.curdir,
            self.backup_folder_path
        ))

        assert os.path.isdir(output_dir), 'Directory %s can\'t be found.' % output_dir

        output_dir = os.path.abspath(os.path.join(output_dir, '%s__%s'% (self.database_name, today.strftime('%Y_%m_%d_%H%M%S'))))

        #logging.info('Backing up %s from %s to %s' % (db, hostname, output_dir))

        backup_output = subprocess.check_output(
            [
                'mongodump',
                '--host', '%s' % self.host,
                '--username', '%s' % self.user,
                '--password', '%s' % self.password,
                '--ssl',
                '--authenticationDatabase', 'admin',
                '--db', '%s' % self.database_name,
                '-o', '%s' % output_dir
            ]
        )
        logging.info(backup_output)
        self.zip_name = os.path.basename(shutil.make_archive(self.backup_folder_path, 'zip', self.backup_folder_path))
        self.backup_to_minio()
    # End backup_mongodump()
# End class

def pairwise(iterable):
    """Returns every two elements in the given list
    
    Arguments:
        iterable {list} -- The input List
    """    

    """ """
    a = iter(iterable)
    return zip(a, a)
# End pairwise

def file_parse(file) -> None:
    """Parses the given file (If applicable) """

    fp = open(file, 'r')

    # Allows for different formatting of the options
    connection_string_variants = ["mongo_connection", "connection_string", "conn", "mongo_connection_string", "MongoConnection"]
    db_name_variants = ["database", "name", "database_name", "db", "MongoDatabase", "mongo_database", "MongoDB", "MongoDb"]
    access_variants = ["access_key", "access", "accesskey", "accessKey"]
    secret_variants = ["secret", "secret_key", "secretKey"]
    mongo_host_variants = ["host", "mongo_host", "Host", "MongoHost"]
    mongo_pass_variants = ["pass", "password", "MongoPass", "mongo_pass", "MongoPassword", "Password", "mongo_password"]
    mongo_port_variants = ["port", "mongo_port", "MongoPort", "Port"]
    mongo_user_variants = ["User", "user", "MongoUser", "mongo_user"]
    minio_endpoint_variants = ["MinioEndpoint", "Endpoint", "minio_endpoint", "endpoint"]
    minio_bucket_variants = ["MinioBucket", "Bucket", "minio_bucket", "bucket", "BucketName"]
    minio_location_variants = ["MinioLocation", "minio_location", "location"]

    conn_string = None
    db = None
    access = None
    secret = None
    mongo_host = None
    mongo_user = None
    mongo_pass = None
    mongo_port = None
    minio_bucket = None
    minio_location = None
    minio_endpoint = None
    for line in fp:
        arg_list = line.split('=', 1)
        for arg, val in pairwise(arg_list):
            if arg in connection_string_variants:
                conn_string = val.strip()
            elif arg in db_name_variants:
                db = val.strip()
            elif arg in access_variants:
                access = val.strip()
            elif arg in secret_variants:
                secret = val.strip()
            elif arg in mongo_host_variants:
                mongo_host = val.strip()
            elif arg in mongo_pass_variants:
                mongo_pass = val.strip()
            elif arg in mongo_port_variants:
                mongo_port = val.strip()
            elif arg in mongo_user_variants:
                mongo_user = val.strip()
            elif arg in minio_endpoint_variants:
                minio_endpoint = val.strip()
            elif arg in minio_bucket_variants:
                minio_bucket = val.strip()
            elif arg in minio_location_variants:
                minio_location = val.strip()
    
    mongo = MongoBackup(mongo_host, mongo_user, mongo_pass, mongo_port, access, secret, conn_string, db, minio_endpoint, minio_bucket, minio_location )
    fp.close()
    mongo.backup_mongodump()
    
# End file_parse 

def main():
    argument_list = sys.argv[1:]
    short_options = "f"
    options = [
            "file="
            ]

    try:
        arguments, values = getopt.getopt(argument_list, short_options, options)
    except getopt.error as err:
        print(str(err))
        sys.exit(2)

    # Declare variables for use later
    file = None
    # Loop through the arguments and assign them to our variables
    for curr_arg, curr_val in arguments:
        if curr_arg in ("-f", "--file"):
            file = curr_val
    if file is None:
        print('ERROR: Need input file')
        print('Usage example: python3 MongoBackup.py --file=credentials.txt')
    else:
        print('starting backup process...')
        file_parse(file)
    
# End main

if __name__ == "__main__":
    main()
