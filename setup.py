from setuptools import setup, find_packages
with open('README.md', encoding="utf-8") as readme_file:
    README = readme_file.read()

with open('HISTORY.md', encoding="utf-8") as history_file:
    HISTORY = history_file.read()

setup_args = dict(
    name='qsea',
    version='0.1.18',
    description='Convenient way to work with Qlik Sense Engine API from Python',
    long_description_content_type="text/markdown",
    long_description=README + '\n\n' + HISTORY,
    license='MIT',
    packages=find_packages(),
    author='Lev Biriukov',
    author_email='lbiryukov@gmail.com',
    keywords=['QlikSense', 'Qlik'],
    url='https://github.com/ncthuc/qsea',
    download_url='https://pypi.org/project/qsea/'
)

install_requires = ['pandas', 'datetime', 'websocket-client']

if __name__ == '__main__':
    setup(**setup_args, install_requires=install_requires)	