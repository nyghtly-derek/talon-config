import logging
import os
import shutil
import warnings
from pathlib import Path

from talon import Context, Module, actions, app, clip, cron, imgui, resource, ui

from .user_settings import DATA_DIR, SETTINGS_DIR

########################################################################
# global settings
########################################################################
# if quick_replace, then when a word is selected and only one homophone exists,
# replace it without bringing up the options
quick_replace = True
show_help = False
########################################################################

ctx = Context()
mod = Module()
mod.mode("homophones")
mod.list("homophones_canonicals", desc="list of words ")

main_screen = ui.main_screen()

all_homophones = {}
def get_homophones_from_csv(filename: str):
    """Retrieves homophones from CSV"""
    # todo this code could be consolidated, save for parsing, with user_settings.
    path = SETTINGS_DIR / filename
    template_name = filename + ".template"
    template_path = DATA_DIR / template_name
    cwd = os.path.dirname(os.path.realpath(__file__))
    legacy_path = Path(os.path.join(cwd, "homophones.csv"))
    # print(str(legacy_path))
    assert filename.endswith(".csv")
    if not path.is_file():
        if legacy_path and legacy_path.is_file():
            shutil.move(legacy_path, path)
            warnings.warn(
                "Support for the legacy CSVs location (i.e. outside /Settings) will be removed in the Talon v0.2.0 timeframe. Moving file from {} to {}".format(
                    legacy_path, path
                ),
                DeprecationWarning,
            )
        else:
            assert template_path.is_file()
            shutil.copyfile(template_path, path)

    phones = {}
    canonical_list = []
    with resource.open(str(path), "r") as f:
        for line in f:
            words = line.rstrip().split(",")
            canonical_list.append(words[0])
            for word in words:
                word = word.lower()
                old_words = phones.get(word, [])
                phones[word] = sorted(set(old_words + words))

    global all_homophones
    all_homophones = phones
    #print(str(all_homophones))
    return canonical_list

def on_ready():
    get_homophones_from_csv("homophones.csv")


app.register("ready", on_ready)

active_word_list = None
is_selection = False


def close_homophones():
    gui.hide()
    actions.mode.disable("user.homophones")


PHONES_FORMATTERS = [
    lambda word: word.capitalize(),
    lambda word: word.upper(),
]

def find_matching_format_function(word_with_formatting, format_functions):
    """ Finds the formatter function from a list of formatter functions which transforms a word into itself.
     Returns an identity function if none exists """
    for formatter in format_functions:
        formatted_word = formatter(word_with_formatting)
        if word_with_formatting == formatted_word:
            return formatter

    return lambda word: word


def raise_homophones(word_to_find_homophones_for, forced=False, selection=False):
    global quick_replace
    global active_word_list
    global show_help
    global force_raise
    global is_selection

    force_raise = forced
    is_selection = selection

    if is_selection:
        word_to_find_homophones_for = word_to_find_homophones_for.strip()

    formatter = find_matching_format_function(word_to_find_homophones_for, PHONES_FORMATTERS)

    word_to_find_homophones_for = word_to_find_homophones_for.lower()

    if word_to_find_homophones_for not in all_homophones:
        app.notify("homophones.py", '"%s" not in homophones list' % word_to_find_homophones_for)
        return

    valid_homophones = all_homophones[word_to_find_homophones_for]

    # Move current word to end of list to reduce searcher's cognitive load
    valid_homophones_reordered = (
        list(
            filter(
                lambda word_from_list: word_from_list.lower() != word_to_find_homophones_for, valid_homophones)
        ) + [word_to_find_homophones_for]
    )
    active_word_list = list(map(formatter, valid_homophones_reordered))

    if (
            is_selection
            and len(active_word_list) == 2
            and quick_replace
            and not force_raise
    ):
        if word_to_find_homophones_for == active_word_list[0].lower():
            new = active_word_list[1]
        else:
            new = active_word_list[0]

        clip.set(new)
        actions.edit.paste()

        return

    actions.mode.enable("user.homophones")
    show_help = False
    gui.show()


@imgui.open(x=main_screen.x + main_screen.width / 2.6, y=main_screen.y)
def gui(gui: imgui.GUI):
    global active_word_list
    if show_help:
        gui.text("Homephone help - todo")
    else:
        gui.text("Select a homophone")
        gui.line()
        index = 1
        for word in active_word_list:
            if gui.button("Choose {}: {}".format(index, word)):
                actions.insert(actions.user.homophones_select(index))
                actions.user.homophones_hide()
            index = index + 1

        if gui.button("Phones hide"):
            actions.user.homophones_hide()


def show_help_gui():
    global show_help
    show_help = True
    gui.show()


@mod.capture(rule="{self.homophones_canonicals}")
def homophones_canonical(m) -> str:
    "Returns a single string"
    return m.homophones_canonicals


@mod.action_class
class Actions:
    def homophones_hide():
        """Hides the homophones display"""
        close_homophones()

    def homophones_show(m: str):
        """Show the homophones display"""
        print(m)
        raise_homophones(m, False, False)

    def homophones_show_selection():
        """Show the homophones display for the selected text"""
        raise_homophones(actions.edit.selected_text(), False, True)

    def homophones_force_show(m: str):
        """Show the homophones display forcibly"""
        raise_homophones(m, True, False)

    def homophones_force_show_selection():
        """Show the homophones display for the selected text forcibly"""
        raise_homophones(actions.edit.selected_text(), True, True)

    def homophones_select(number: int) -> str:
        """selects the homophone by number"""
        if number <= len(active_word_list) and number > 0:
            return active_word_list[number - 1]

        error = "homophones.py index {} is out of range (1-{})".format(
            number, len(active_word_list)
        )
        app.notify(error)
        raise error

    def homophones_get(word: str) -> [str] or None:
        """Get homophones for the given word"""
        word = word.lower()
        if word in all_homophones:
            return all_homophones[word]
        return None
