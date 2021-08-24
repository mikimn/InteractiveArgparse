import setuptools

setuptools.setup(
    name='InteractiveArgparse',
    version='0.0.1',
    author='Miki Mendelson-Mints',
    author_email='mikimn1999@gmail.com',
    description='Effortlessly turn any ArgumentParser script into an interactive prompt.',
    url='https://github.com/mikimn/arggo',
    packages=setuptools.find_packages(),
    install_requires=[
        'setuptools',
    ],
    include_package_data=True,
    python_requires='>=3.7'
)
