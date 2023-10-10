# elena
A collection of tools for Doom Eternal map .entities files.

Includes: map entities file parser, writer, oodle (de)compression wrapper,
indexer and a Qt6 based graphical user interface.

I wrote this program mainly for myself. I released it to the public in
the hope that it may be useful for others.

Author: alveraan (accounts@alveraan.com)
License: GPLv3 (see LICENSE.txt)

Limitations
-----------
- GUI: More than one entity with the same name in the same file is not
  supported. The last such entity will overwrite any other with the
  same name.
- GUI: Drap and Drop of entities is currently not supported.
- Comments are removed when parsing, so they cannot be saved back
  into a file nor shown in the gui.

Installation
------------
If you're using a packaged version of the GUI (e.g. an .exe file on Windows),
no installation is needed. Simply execute the exe file. Do not delete the
"_internal" directory, it is required.
To be able to open/save oodle compressed files, you have to copy the file
oo2core_8_win64.dll from your Doom Eternal installation directory to the
same directory the exe file is in.

If you're dealing with the source version, continue reading below.

1. Prerequisites
You need a recent Python version (tested with 3.10 and 3.11). The python
executable has to be in your PATH, meaning of you open a command prompt /
terminal window, and type python, you should get an interactive python
prompt.

On Linux, you also need Qt6 to run the GUI. The Qt6-base package,
available in various distributions, should suffice.

2. Windows-Installation
Double click on the install.bat file. This will prepare a python
virtual environment for you and install the required packages into it.

To be able to open and save compressed map .entities file, you have to
copy the file oo2core_8_win64.dll from your Doom Eternal installation
directory to the "elena" subdirectory inside the program directory.
So if your program was installed in c:\Elena, copy the file to
c:\Elena\elena

3. Linux installation
- Open a terminal as non root user. Go to the directory where this
program is located (where this README.txt document is located).
- Create the virtual environment:
  $ python -m venv linux-env
- Activate the virtual environment:
  $ . linux-env/bin/activate
  You should now see "(linux-env)" at the beginning of your prompt.
- Install required python packages:
  $ pip install -r requirements.txt

To be able to open and save compressed map .entities file, you have to
copy the file liblinoodle.so to the "elena" subdirectory inside the
program directory. So if your program was installed in
/home/youruser/Elena, copy the file to /home/youruser/Elena/elena

Starting the GUI
----------------
If you have an exe file, simple double click that. Otherwise...

1. Windows
Double click on start_gui.bat

2. Linux
- Open a terminal as non root user. Go to the directory where this
  program is located (where this README.txt document is located).
- Activate the virtual environment:
  $ . linux-env/bin/activate
  You should now see "(linux-env)" at the beginning of your prompt.
- Change into the elena subdirectoy:
  $ cd elena
- Start gui.py:
  $ python gui.py
  If you want to load a map .entities file using the terminal, you
  can just add the path to the file at the end like this:
  $ python gui.py /path/to/map.entities

GUI usage
---------
Here are some tips for the GUI:
- Please make backups of your entities files. I cannot guarantee that this
  program won't corrupt your files or delete information in them.
- If you get a parse error, check the syntax of your entities (missing
  semicolons, missing equals signs, missing entityDef declaration etc).
- After opening a file, you can right click on an entity in the list to see
  available actions like bookmark, insert from file, export to file etc.
- Changes to the code of an entity are saved to memory only after clicking
  "Save" under the code widget on the right. Changes are only saved to a
  file when using File -> Save As... (CTRL+S).
- If "Apply filters" is checked, filters that use Comboboxes like
  "Layers" and "Classes" are applied as soon as you change the
  selection in the Combobox. To apply filters that use a text input like
  for spawn position, key and value, simply type the value followed by
  ENTER.
- You can directly copy paste a position from spawnPosition
  assignments inside the entity into the x, y or z input fields. For
  example, if you paste this text:
    spawnPosition = {
        x = 250.5;
        y = -740.750061;
        z = -188.250015;
    }
  into one of the three fields, x will get the value 250.5, x will get
  -740.750061 and z -188.250015.
  Just pasting
    x = 250.5;
    y = -740.750061;
    z = -188.250015;
  also works.
  You can also use the mh_spawninfo command provided by meath00k
  inside the Doom Eternal console, which will copy the current
  coordinates into your clipboard. You can then paste them inside one of the
  three fields (x, y or z).
- If you want to clear/empty the spawn position fields (x, y and z),
  just press ESCAPE in one of those fields.
- For bookmarks: rightclick on entity -> Bookmark to add a new bookmark.
  Select a bookmark in the list and click edit to change its name. Click
  Remove to delete the bookmark. Double click on a bookmark to jump to the
  corresponding entity in the entity list.
- Bookmarks are remembered based on the filename. The bookmarks are saved
  when you save a file, open a new file or close the application while a
  file is open. Bookmarks are saved in bookmarks.json.
- You can let the program fix item arrays by choosing "Edit" ->
  "fix item arrays in editor text". Note that the text must be
  parsable, meaning it must have valid entity syntax.

Further info
------------
I suggest joining the "Doom 2016+ Modding" Discord. You will find all
the information on how to extract map .entities file and on modding
Doom Eternal in general. As of this writing in November 2023, I am active on
that server.