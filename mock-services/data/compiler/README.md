Data for mock compiler service. 

Current implementation (simple): 

At the current time the mock compiler provides an example compilation
log (autotex.log) and a PDF. These samples files come from processing the
upload2.tar.gz example submission (from file manager 
'tests/test_files_upload' directory).

Think about documenting/allowing user to plug in their own files. 
Developer may simply replace the included files.

Future possibilities:

It may be possible to key different 'results' off of the
submission identifier, assuming the development server uses
sequential identifiers like 1, 2, 3...

Each submission might highlight different issues resulting from
compilation.
