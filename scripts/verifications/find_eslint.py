import os

def find_files(directory, pattern):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if pattern in file:
                print(os.path.join(root, file))

find_files('.', 'eslint')
