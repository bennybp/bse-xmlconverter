"""
Garbage and convoluted code attempting to parse the formless REF data using web of science.
"""

import glob
import difflib
import json
from xml.etree import ElementTree as ET

# Locals
import metadata as md

DO_PRINT = True
DO_PRINT = False

STRICT = True
STRICT = False

def string_remove_chars(chars, string):
    for x in chars:
        string = string.replace(x, "")
    return string


def is_number(val):
    try:
        return int(val)
    except ValueError:
        return False


def _read_file(infile, return_raw=False):
    """
    Pulls in the 'notes' line from the REF files and strips the citations into a single line
    """
    root = ET.parse(infile).getroot()
    data = root.findall("default:notes", {"default": "http://purl.oclc.org/NET/EMSL/BSE"})[0].text
    if return_raw:
        return data

    if DO_PRINT:
        print(data.strip())
        print("----------\n")
    sldata = data.splitlines()

    ret = []

    inside_refs = False

    for line in sldata:
        # if "Original"line: continue
        # if "Recontraction" in line: continue
        if (":" in line) and not (("DOI:" in line) and (line.count(":") == 1)):
            inside_refs = True
            tmp = line.split(":", 1)
            #if len(tmp) != 2:
            #    raise ValueError("Citation list must have only two elements on each side of ':'\n"
            #                     "    Found: %s" % line)
            ret.append((tmp[0].strip(), tmp[1].strip()))
        elif inside_refs:
            ret[-1] = (ret[-1][0], ret[-1][1] + " " + line.strip())

    #for x in ret:
    #    print(x[1])
    return data, ret


def _handle_atoms(atoms):
    """
    Provides a Z list for the atom string
    >>> _handle_atom("He-Li")
    [2, 3]
    """
    if "," in atoms:
        atoms = [x.strip() for x in atoms.split(",")]
    elif " " in atoms and ("-" not in atoms):
        atoms = atoms.split(" ")
    else:
        atoms = [atoms.strip()]

    ret = []
    for at in atoms:
        if len(at.strip()) == 0: continue
        if "-" in at:
            start, stop = at.split("-")
            start = md.atom_symbol_to_number[start.strip().upper()]
            stop = md.atom_symbol_to_number[stop.strip().upper()]

            ret.extend(list(range(start, stop + 1)))
        else:
            ret.append(md.atom_symbol_to_number[at.strip().upper()])
    ret.sort()
    return ret


def _handle_cit(citation):
    """
    Decomposes a citation string into a series of fields
    """
    DO_PRINT = False

    ret = {"original": citation.strip(), "valid": False}

    # Filter out incomplete
    for err in ["to be published", "submitted", "unpublished", "unofficial", "private com"]:
        if err in citation.lower():
            ret["valid"] = "unpublished"
            return ret

    if len(citation.strip()) < 5:
        return ret

    #print("CIT, %s" %citation)
    #if DO_PRINT:
    #    print(citation)

    tmp = citation.split(" DOI:")
    if len(tmp) == 1:
        citation = tmp[0]
    elif len(tmp) == 2:
        citation = tmp[0]
        ret["DOI"] = tmp[1].strip()
    else:
        raise KeyError("Unpack DOI not understood: %s" % str(tmp))

    citation = citation.replace(" -", "-")

    ### Try to find Y/P/V
    ypv_citation = citation.split()
    if ypv_citation[-2].lower() == "accepted":
        ypv_citation[-2] = "0"
        ypv_citation[-3] = "0"

    ret["year"] = is_number(string_remove_chars("().,", ypv_citation[-1]))
    ret["page"] = is_number(string_remove_chars("().,", ypv_citation[-2]).split('-')[0])
    ret["volume"] = is_number(string_remove_chars("().,", ypv_citation[-3]))

    ypv_data = [ret[x] is False for x in ["year", "page", "volume"]]
    if any(ypv_data):
        raise KeyError("Could not find year/page/volume: %s" % citation)

    citation = " ".join(ypv_citation[:-3])
    if DO_PRINT:
        print(1, citation)

    ### Yank out authors

    # Hack our Jr's
    citation = citation.replace(" Jr.", "")
    authors = []
    break_next = False
    author_enumerate = citation.replace(" and ", ",   ")
    author_enumerate = author_enumerate.replace(",and", ",  ")

    chars_used = 0
    for num, sp in enumerate(author_enumerate.split(",")):
        sp_chars = len(sp) + 1

        # Are we nothing?
        sp = sp.strip()
        if len(sp) == 0:
            chars_used += sp_chars
            continue

        # Watch cases
        isjournal = difflib.get_close_matches(sp, md.known_journals, cutoff=0.8)
        if isjournal:
            break

        # If we hit a `and` we will be done next iteration
        if break_next:
            break

        if (" and " in sp) or (",and " in sp):
            break_next = True

        # Authors should have a "." in their name
        if (("." in sp) and (len(sp) < 80)) or difflib.get_close_matches(sp, md.known_authors):
            chars_used += sp_chars
            authors.append(sp)
        else:
            break

    # Cleanup authors
    authors = [string_remove_chars([")", "(", ",and", " and ", ","], x).strip() for x in authors]

    ret["authors"] = authors

    # Move on to journal/title

    citation = citation[chars_used:].strip()
    if DO_PRINT:
        print(citation)

    citation = citation.replace("  ", " ")
    citation = citation.replace("  ", " ")
    citation = citation.strip()
    if citation.startswith(","):
        citation = citation[1:]
    if citation.endswith(","):
        citation = citation[:-1]
    if DO_PRINT:
        print(2, citation)

    # Split from the left by 1, then unpack, ugh
    #print(remain)
    remain = citation[::-1].split(",", 1)
    remain = [x[::-1].strip() for x in remain][::-1]
    remain = [x for x in remain if len(x)]
    if DO_PRINT:
        print(remain)

    # Journal/Title
    ret["journal"] = False
    ret["title"] = False
    if (len(remain) == 1) and difflib.get_close_matches(remain[0].strip(), md.known_journals, cutoff=0.8):
        ret["journal"] = remain[0].strip()
    elif len(remain) >= 2:
        ret["journal"] = remain[-1].strip()
        ret["title"] = remain[0].strip()
    else:
        print(json.dumps(ret, indent=4))
        print(ret["original"])
        print(remain)
        raise Exception()

    ret["valid"] = True
    return ret


def _parse_citation(atoms, cit):

    ret = {}
    ret["Z"] = _handle_atoms(atoms)
    ret.update(_handle_cit(cit))
    #try:
    #except:
    #    ret["original"] = cit.strip()
    #    ret["valid"] = False

    if STRICT and (ret["valid"] is False):
        del ret["Z"]
        raise Exception("Error in \n%s" % json.dumps(ret, indent=4))

    if DO_PRINT:
        print('---------')
        print(cit)
        for k, v in ret.items():
            print("%10s : %s" % (k, v))
        print('---------')
    return ret


def parse_ref_file(infile):
    ret = {}
    # Parse
    data, cit_list = _read_file(infile)
    ret["original"] = data

    if len(cit_list) == 0:
        raise KeyError("No citations for %s" % infile)

    citations = []
    for atoms, cit in cit_list:
        json_cit = _parse_citation(atoms, cit)
        citations.append(json_cit)
    ret["citations"] = citations

    return ret


# Quick tests

failures = 0
success = 0
for infile in glob.glob("../data/xml_stage/*REF.xml"):
#for infile in glob.glob("../data/xml_stage/6-31PGSS-BS-REF.xml"):
#for infile in glob.glob("../data/xml/*REF.xml"):
#for infile in glob.glob("../data/xml/CC-PVQZ-DK-BS-REF.xml"):
    #print(infile)

    json_data = parse_ref_file(infile)
#    raise Exception()
    try:
        json_data = parse_ref_file(infile)
        json_data["valid"] = True
        #print(json.dumps(json_data, indent=4, sort_keys=True))
        success += 1
    except Exception as err:
        print("Failed: %s" % infile)
        # print(repr(err))
        failures += 1
        json_data = {"valid": False}
        try:
            json_data["original"] = _read_file(infile, return_raw=True)
        except IndexError:
            print("Truly FUBAR: %s" % infile)
            json_data["original"] = "FUBAR"

    name = infile.split('/')[-1].replace("xml", "json")
    with open("stage1/" + name, "w") as outfile:
        json.dump(json_data, outfile, indent=4, sort_keys=True)

#        print(json.dumps(json_data, indent=4, sort_keys=True))

#    raise

print("Success %d, Failures %d,  Ratio %3.2f" % (success, failures, success / (failures + success)))
