from setuptools import setup, find_packages

setup(
    name="vxpolls",
    version="0.1.0",
    url='http://github.com/praekelt/vxpolls',
    license='BSD',
    description="Simple polling / survey framework for Vumi apps",
    long_description=open('README.rst', 'r').read(),
    author='Praekelt Foundation',
    author_email='dev@praekeltfoundation.org',
    packages=find_packages(),
    install_requires=[
        'vumi',
    ],
    classifiers=[
        'Development Status :: 7 - Inactive',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
