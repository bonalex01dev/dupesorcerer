HASH

This software helps remove duplicates from a big number of files. For now
comparison is based on name and file size being identical. We will
add the possibility to ceate a hash for each file to compare on the
content of the file instead. - For this a radio button choice at the
top of window should be added to choose between "name+size"
or "content (hash)". the value should be strored in the
"test_content" boolean. - the buttons should be hidden when
processing begins - when entering the comparison loop each file
should have it's hash calculated if "test_content" is true
and this hash should be used instead of name and size for duplicates
identification. Before any modifications of the code, suggest me for
the choices of librarys available for the hash processing. We want
something simple. Before modifying the code, read the whole file to
make sure the duplicates are not identified by their name anywhere in
the code, but by position in the list or anything else to make sure
switching to a hash value will not break anything



LAST COPY PROTECTION

this software helps remove duplicates from a big number of files.
During the final stage, when the files are being physically deleted
there is a detection mechanism in case the program is about to delete
all files instead of keeping at least one copy. This mechanism should
be modified. instead of keeping the last copy, the program should do
this:

-detect the anomaly before deleting any of the duplicates (detect
that all copies are about to be deleted)

- show the user the different folder names, and for each, show
  radio button "keep" and "delete" that are
  mutually exclusive. By default, only the first folder should be in
  the state "keep".

also show buttons "resume process" (default choice can
be activated with return key press) and "cancel" at the
bottom of the interface.

- when "resume process" or "cancel" is
  pressed, check that at least one folder is in "keep" state.
  If not, put the first folder in the "keep" state.

- if "resume process" was selected, proceed with
  deletions and continue the loop to the next file.

- if "cancel" was selected end all processing.

PROGRAM DESCRIPTION

this software helps remove duplicates from a big number of files.

10 : user selects the folder to be analysed and the
comparison mechanism (name+size/ hash value)

20 : duplicate files are identified

30 : For each folder « current folder »
containing duplicates, user is asked to choose which of duplicates
should be « keep » or « remove ». the choice
is made for « current folder » and the « other
duplicates folders »

40 : The duplicates are removed based on the choices made by
the user.

- a log in the printed in the main window during deletions

- In case all duplicates are flagged for deletion, a protection
  mechanism detect the situation before any deletion of that one file
  and asks the user to choose the copy to be kept

The protection situation is memorized ( ie. List of folders
containing the duplicates) This allows the « apply to all »
button to process all duplicates in the same situation to be
processed automatically without asking to the user the same question
multiple times.

QUESTION

This program works pretty well. But in some cases in step « 30 »
one « current folder » is displayed but there is no
« other duplicates folders » shown. Try do determine what
can determine this behavior. This behavior could be triggered by
duplicate files with different names in the same folder but it is not
the case i experienced. Find an other explanation.

For now do not modify the code only determine the possible cause
of the problem.

CASE

Related Folders Have Already Been Processed: The code also checks
if a potential related folder's status (related_obj.todo) is still 1
("Ne rien faire") before displaying it (line 429). If the
folders containing the corresponding duplicates have already been
assigned an action ("Effacer" or "Garder")
earlier in the review process (either as a "current folder"
or as a "related folder" to a previous one), their todo
status would no longer be 1. Therefore, they wouldn't be shown again
as "related" to the current folder, even if they contain
matching duplicates.

MULTI KEEP LAST

I want to add a modification to the program.

When the protection mechanism for the case of "all duplicates
files suppression" is triggered and the popup window is asking
the user to keep one copy, the behavior should be changed.

For now the buttons allows to select only one file location to be
marked as "keep". The behavior should be changed to allow
at least one "keep", but also potentially multiple "keep".
For the rest, the behavior of the program should not be changed. In
particular, if the button "conserver appliquer a tous" is
pressed, make sure that, when the same "behaviors" is
triggered again later, the case of multiple "keep" folders
is processed correctly. For this you should check first that the
"behaviors" structure is able to store multiple "keep"
states.
