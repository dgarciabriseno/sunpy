"""
This module provides a JPEG 2000 file reader.
"""
import os
from xml.etree import cElementTree as ET

from sunpy.io.header import FileHeader
from sunpy.util.io import HDPair, string_is_float
from sunpy.util.xml import xml_to_dict

__all__ = ['read', 'get_header', 'write']


def read(filepath, **kwargs):
    """
    Reads a JPEG2000 file.

    Parameters
    ----------
    filepath : `str`
        The file to be read.
    **kwargs : `dict`
        Unused.

    Returns
    -------
    `list`
        A list of (data, header) tuples.
    """
    # Put import here to speed up sunpy.io import time
    from glymur import Jp2k

    header = get_header(filepath)
    data = Jp2k(filepath)[...][::-1]
    return [HDPair(data, header[0])]


def get_header(filepath):
    """
    Reads the header from the file.

    Parameters
    ----------
    filepath : `str`
        The file to be read.

    Returns
    -------
    `list`
        A list of one header read from the file.
    """
    # Put import here to speed up sunpy.io import time
    from glymur import Jp2k
    jp2 = Jp2k(filepath)
    xml_box = [box for box in jp2.box if box.box_id == 'xml ']
    xmlstring = ET.tostring(xml_box[0].xml.find('fits'))
    pydict = xml_to_dict(xmlstring)["fits"]

    # Fix types
    for k, v in pydict.items():
        if v.isdigit():
            pydict[k] = int(v)
        elif string_is_float(v):
            pydict[k] = float(v)

    # Remove newlines from comment
    if 'comment' in pydict:
        pydict['comment'] = pydict['comment'].replace("\n", "")

    # Is this file a Helioviewer Project JPEG2000 file?
    pydict['helioviewer'] = xml_box[0].xml.find('helioviewer') is not None

    return [FileHeader(pydict)]

def header_to_xml(header):
    """
    Converts image header metadata into an XML Tree that can be inserted into
    a JP2 file header.

    Parameters
    ----------
    header : `MetaDict`
        A header dictionary.
    """
    # glymur uses lxml and will crash if trying to use
    # python's builtin xml.etree
    import lxml.etree as ET

    fits = ET.Element("fits")

    already_added = set()
    for key in header:
        # Some headers span multiple lines and get duplicated as keys
        # header.get will appropriately return all data, so if we see
        # a key again, we can assume it was already added to the xml tree.
        if (key in already_added):
            continue

        # Add to the set so we don't duplicate entries
        already_added.add(key)

        el = ET.SubElement(fits, key)
        data = header.get(key)
        if type(data) == bool:
            data = "1" if data else "0"
        else:
            data = str(data)

        el.text = data

    return fits

def generate_jp2_xmlbox(header):
    """
    Generates the JP2 XML box to be inserted into the jp2 file.

    Parameters
    ----------
    header : `MetaDict`
        A header dictionary.
    """
    # glymur uses lxml and will crash if trying to use
    # python's builtin xml.etree
    import lxml.etree as ET
    from glymur import jp2box

    header_xml = header_to_xml(header)
    meta = ET.Element("meta")
    meta.append(header_xml)
    tree = ET.ElementTree(meta)
    return jp2box.XMLBox(xml=tree)

def get_tmp_jp2_file_name(filename):
    """
    Returns a temporary file name for jp2 files since creating
    a JP2 file with the correct header takes 2 passes.
    """
    return filename + ".tmp.jp2"

def write(fname, data, header):
    """
    Take a data header pair and write a JP2 file.

    Parameters
    ----------
    fname : `str`
        File name, with extension.
    data : `numpy.ndarray`
        n-dimensional data array.
    header : `dict`
        A header dictionary.
    """
    import numpy as np
    from glymur import Jp2k

    # Create an initial jp2 file with the given data
    tmpname = get_tmp_jp2_file_name(fname)
    jp2_data = np.uint8(data)
    jp2 = Jp2k(tmpname, jp2_data)

    # Append the XML data to the headerp information
    meta_boxes = jp2.box
    target_index = len(meta_boxes) - 1
    fits_box = generate_jp2_xmlbox(header)
    meta_boxes.insert(target_index, fits_box)

    # Rewrite the jp2 file with the xml data in the header
    jp2.wrap(fname, boxes=meta_boxes)

    # Remove the initial temporary file
    os.remove(tmpname)

