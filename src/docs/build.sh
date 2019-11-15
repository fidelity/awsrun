#!/bin/sh

OUTDIR=../../docs

# Build docs from python docstrings
pdoc --template-dir=templates --html -o ${OUTDIR} ../awsrun
mv 	${OUTDIR}/awsrun/* ${OUTDIR}
rmdir ${OUTDIR}/awsrun

# Move static content into place
cp screencast/demo.svg ${OUTDIR}
