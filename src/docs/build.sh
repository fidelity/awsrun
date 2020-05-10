#!/bin/bash

# Make sure we are in the directory where the script is located
cd $( dirname "${BASH_SOURCE[0]}" )

OUTDIR=../../docs

# Remove old contents of the docs directory
rm -rf ${OUTDIR}/*

# Build docs from python docstrings
pdoc --template-dir=templates --html -o ${OUTDIR} ../awsrun

# pdoc always outputs to a dir called awsrun, but we want that
# content in the docs directory
mv ${OUTDIR}/awsrun/* ${OUTDIR}
rmdir ${OUTDIR}/awsrun

# Move static content into place
cp images/* ${OUTDIR}
cp screencast/demo.svg ${OUTDIR}
cp webfonts/webfonts.css ${OUTDIR}

