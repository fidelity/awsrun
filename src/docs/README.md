# API Documentation

The API documentation is built with <https://pdoc3.github.io/pdoc/>. This can be
installed via:

    pip3 install pdoc3 --user

Once installed, the HTML docs can be generated via:

    pdoc --template-dir=src/docs/templates --html -o docs/ src/awsrun

from the projects top-level directory. This will produce a directory called
`awsrun` in the `docs` directory.

While developing, it is useful to run the built-in web server, so you can see
how your docstrings will be rendered via:

    pdoc --template-dir=src/docs/templates --http : awsrun
