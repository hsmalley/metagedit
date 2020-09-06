#coding=utf-8

# =============================================================================================
# This program is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either version
# 3 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# This script must/should come together with a copy of the GNU General Public License. If not,
# access <http://www.gnu.org/licenses/> to find and read it.
#
# Author: Pedro Vernetti G.
# Name: Metagedit
# Description: gedit plugin which adds multiple improvements and functionalities to it
#
# #  In order to have this script working (if it is currently not), run 'install.sh'.
# =============================================================================================

import codecs, random, re
from unicodedata import normalize as unicodeNormalize, combining as unicodeCombining
from urllib.parse import quote as urlquote, unquote as urlunquote
import chardet



def getSelection( document, noSelectionMeansEverything=True ):
    if (not document.get_has_selection()):
        if (noSelectionMeansEverything): # get whole document
            beg, end = (document.get_start_iter(), document.get_end_iter())
        else: # get current character
            beg = document.get_iter_at_mark(document.get_insert())
            end = document.get_iter_at_mark(document.get_insert())
            end.forward_char()
        return (beg, end, True)
    beg, end = document.get_selection_bounds()
    return (beg, end, False)



def getSelectedLines( document, noSelectionMeansEverything=True ):
    if (not document.get_has_selection()):
        if (noSelectionMeansEverything): # get whole document
            beg, end = (document.get_start_iter(), document.get_end_iter())
            return (beg, end, True)
        else: # get current line
            line = document.get_iter_at_mark(document.get_insert()).get_line()
            end = document.get_iter_at_line(line)
            end.forward_line()
            return (document.get_iter_at_line(line), end, True)
    beg, end = document.get_selection_bounds()
    if (beg.ends_line()): beg.forward_line()
    elif (not beg.starts_line()): beg.set_line_offset(0)
    if (end.starts_line()): end.backward_char()
    elif (not end.ends_line()): end.forward_to_line_end()
    return (beg, end, False)



def removeTrailingSpaces( document, onSaveMode=False ):
    ## REMOVE TRAILING SPACES
    trailingSpaces = r'[\f\t \u2000-\u200A\u205F\u3000]+$'
    if (onSaveMode):
        beg, end, noneSelected = (document.get_start_iter(), document.get_end_iter(), True)
    else:
        beg, end, noneSelected = getSelectedLines(document)
    selection = document.get_text(beg, end, False)
    document.begin_user_action()
    if (noneSelected): # whole-document mode (doesn't move the cursor)
        lineNumber = 0
        for line in selection.splitlines():
            if (len(line) != 0):
                beg.set_line(lineNumber)
                beg.set_line_offset(len(re.sub(trailingSpaces, r'', line)))
                end.set_line(lineNumber)
                end.set_line_offset(len(line))
                document.delete(beg, end)
            lineNumber += 1
        removeTrailingNewlines(document)
    else: # selection mode
        selection = re.sub(trailingSpaces, r'', selection, flags=re.MULTILINE)
        document.delete(beg, end)
        document.insert_at_cursor(selection)
    document.end_user_action()


def removeTrailingNewlines( document ):
    ## REMOVE TRAILING SPACES
    end = document.get_end_iter()
    if (end.starts_line()):
        while (end.backward_char()):
            if (not end.ends_line()):
                  end.forward_to_line_end()
                  break
    document.delete(end, document.get_end_iter())
    #document.insert(end, "\n") # uncomment to always leave 1 trailing newline



def removeEmptyLines( document ): #TODO: selection mode inserts trailing newlines for some reason
    ## LINE OPERATIONS
    beg, end, noneSelected = getSelectedLines(document)
    document.begin_user_action()
    if (noneSelected): # whole-document mode (doesn't move the cursor)
        for lineNumber in reversed(range(0, (document.get_line_count() - 1))):
            beg.set_line(lineNumber)
            end.set_line(lineNumber)
            if (not end.ends_line()): end.forward_to_line_end()
            if (re.match(r'^\s*$', document.get_text(beg, end, False))):
                end.forward_char()
                document.delete(beg, end)
        removeTrailingNewlines(document)
    else: # selection mode
        beg.backward_char()
        selection = document.get_text(beg, end, False)
        if (re.match(r'^\s*$', selection, flags=re.MULTILINE)): selection = r''
        selection = re.sub(r'\n\s*\n', r'\n', selection, flags=re.MULTILINE)
        document.delete(beg, end)
        document.insert_at_cursor(selection)
    document.end_user_action()



def removeLines( document ):
    ## LINE OPERATIONS
    beg, end, noneSelected = getSelectedLines(document, False)
    if (not noneSelected): beg.backward_char()
    document.begin_user_action()
    document.delete(beg, end)
    document.end_user_action()



def joinLines( document, separatedWithSpaces=True ):
    ## LINE OPERATIONS
    beg, end, noneSelected = getSelectedLines(document)
    selection = document.get_text(beg, end, False)
    selection = re.sub(r'\n\s*\n', r'\n', selection, flags=re.MULTILINE).strip()
    selection = selection.replace('\n', (r' ' if separatedWithSpaces else r''))
    document.begin_user_action()
    document.delete(beg, end)
    document.insert_at_cursor(selection)
    document.end_user_action()



def reverseLines( document ):
    ## LINE OPERATIONS
    beg, end, noneSelected = getSelectedLines(document)
    if (noneSelected):
        cursorPosition = document.get_iter_at_mark(document.get_insert())
        line = document.get_line_count() - (cursorPosition.get_line() + 1)
        column = cursorPosition.get_line_offset()
    selection = document.get_text(beg, end, False).splitlines()
    document.begin_user_action()
    document.delete(beg, end)
    document.insert_at_cursor('\n'.join(reversed(selection)))
    if (noneSelected):
        document.place_cursor(document.get_iter_at_line_offset(line, column))
    document.end_user_action()



def _dedupedLines( selection, caseSensitive=True, offset=0 ): #TODO: [selection mode] inserts trailing newlines for some reason
    ## LINE OPERATIONS
    finalContent = []
    seen = set()
    for line in selection:
        line_ = line[offset:] if caseSensitive else line[offset:].casefold()
        if (line_ not in seen):
            finalContent.append(line)
            seen.add(line_)
    return finalContent



def dedupLines( document, caseSensitive=False, offset=0 ):
    ## LINE OPERATIONS
    beg, end, noneSelected = getSelectedLines(document)
    document.begin_user_action()
    if (noneSelected): # whole-document mode (doesn't move the cursor)
        seen = set()
        for lineNumber in reversed(range(0, document.get_line_count())):
            beg.set_line(lineNumber)
            end.set_line(lineNumber)
            if (not end.ends_line()): end.forward_to_line_end()
            line = document.get_text(beg, end, False)[offset:]
            if (not caseSensitive): line = line.casefold()
            if ((line in seen) or seen.add(line)):
                end.forward_char()
                document.delete(beg, end)
    else: # selection mode
        selection = document.get_text(beg, end, False).splitlines()
        document.delete(beg, end)
        selection = _dedupedLines(selection, caseSensitive, offset)
        document.insert_at_cursor('\n'.join(selection))
    document.end_user_action()



def shuffleLines( document, dedup=False, caseSensitive=False, offset=0 ):
    ## LINE OPERATIONS
    beg, end, noneSelected = getSelectedLines(document)
    selection = document.get_text(beg, end, False).splitlines()
    if (dedup): selection = _dedupedLines(selection, caseSensitive, offset)
    random.shuffle(selection)
    document.begin_user_action()
    document.delete(beg, end)
    document.insert_at_cursor('\n'.join(selection))
    document.end_user_action()



def sortLines( document, reverse=False, dedup=False, caseSensitive=False, offset=0 ):
    ## LINE OPERATIONS
    beg, end, noneSelected = getSelectedLines(document)
    selection = document.get_text(beg, end, False).splitlines()
    if (dedup): selection = _dedupedLines(selection, caseSensitive, offset)
    if (not caseSensitive):
        sortKey = lambda x: re.sub(r'\s+', r'', x[offset:].casefold())
    else:
        sortKey = lambda x: re.sub(r'\s+', r'', x[offset:])
    selection = sorted(selection, key=sortKey)
    if (reverse): selection = reversed(selection)
    document.begin_user_action()
    document.delete(beg, end)
    document.insert_at_cursor('\n'.join(selection))
    document.end_user_action()



def percentEncode( document, doNotEncode=r'' ):
    ## ENCODING STUFF
    beg, end, noneSelected = getSelection(document, False)
    selection = document.get_text(beg, end, False)
    default = r'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~'
    if (noneSelected and (selection in default)): return
    doNotEncode = doNotEncode.replace(r'%', r'')
    document.begin_user_action()
    document.delete(beg, end)
    document.insert_at_cursor(urlquote(selection, doNotEncode, r'utf-8', r'ignore'))
    document.end_user_action()



def percentDecode( document ):
    ## ENCODING STUFF
    beg, end, noneSelected = getSelection(document, False)
    if (noneSelected): end.forward_chars(2)
    selection = document.get_text(beg, end, False)
    if (noneSelected and (not re.match(r'^%[0-9A-Fa-f][0-9A-Fa-f]$', selection))): return
    document.begin_user_action()
    document.delete(beg, end)
    document.insert_at_cursor(urlunquote(selection, r'utf-8', r'replace'))
    document.end_user_action()



def redecode( document, actualEncoding=r'Autodetect', forceASCIIMode=False ):
    ## ENCODING STUFF
    actualEncoding = actualEncoding.strip().replace(r' ', r'_').lower()
    actualEncoding = re.sub (r'^(code[-_]?page|windows)[-_]?', r'cp', actualEncoding)
    actualEncoding = re.sub (r'^mac[-_]?os[-_]?', r'mac', actualEncoding)
    auto = (actualEncoding == r'autodetect')
    try:
        inUseEncoding = codecs.lookup(document.get_file().get_encoding().get_charset()).name
        actualEncoding = None if auto else codecs.lookup(actualEncoding).name
        if (inUseEncoding == actualEncoding): return
        text = document.get_text(document.get_start_iter(), document.get_end_iter(), False)
        text = text.encode(inUseEncoding, r'ignore')
        if (auto):
            actualEncoding = codecs.lookup(chardet.detect(text)[r'encoding']).name
            if (inUseEncoding == actualEncoding): return
    except:
        return
    text = text.decode(actualEncoding, r'replace')
    if (forceASCIIMode):
        text = unicodeNormalize(r'NFKD', text)
        text = r''.join([c for c in text if not unicodeCombining(c)])
    document.begin_user_action()
    document.delete(document.get_start_iter(), document.get_end_iter())
    try:
        document.insert(document.get_end_iter(), text)
        document.end_user_action()
    except:
        document.end_user_action()
        document.undo()