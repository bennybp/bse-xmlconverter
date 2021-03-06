import os
import xml.etree.ElementTree as ET

import bse

ns = { 'default': 'http://purl.oclc.org/NET/EMSL/BSE',
       'cml': 'http://www.xml-cml.org/schema/cml2/core',
       'dc': 'http://purl.org/dc/elements/1.1/',
       'dct': 'http://purl.org/dc/terms/',
       'xlink': 'http://www.w3.org/1999/xlink'
}


def create_json_filename(xmlpath, filetype=None):
    bsdir = os.path.dirname(xmlpath)
    filebase = os.path.basename(xmlpath)
    filename = os.path.splitext(filebase)[0]

    if filetype:
        outfile = "{}.{}.json".format(filename, filetype)
    else:
        outfile = "{}.json".format(filename)
    outfile = os.path.join(bsdir, outfile)
    return outfile


def get_single_node(node, tag):
    a = node.findall(tag, ns)
    if a:
        return a[0]
    else:
        return None


def get_single_text(node, tag):
    a = get_single_node(node, tag)
    if a != None:
        return a.text
    else:
        return None


def get_links(node, tag):
    all_nodes = node.findall(tag, ns)
    if all_nodes:
        return [ a.attrib['{{{}}}href'.format(ns['xlink'])] for a in all_nodes ]
    else:
        return None


def get_single_link(node, tag):
    a = get_links(node, tag)
    if a != None:
        return a[0]
    else:
        return None
    

def read_ref_data(xmlfile):
    root = ET.parse(xmlfile).getroot()
    return get_single_text(root, 'default:notes')


def text_to_cont(txt):
    coefficients = []
    exponents = []

    txt = txt.strip()
    for l in txt.splitlines():
        l = l.split()
        exponents.append(l[0])
        coefficients.append(l[1:])


    for i in coefficients:
        if len(i) != len(coefficients[0]):
            print(coefficients)
            raise RuntimeError('Different number of general contractions')


    coefficients = list(map(list, zip(*coefficients)))
    return (exponents,coefficients)


def text_to_ecpcont(txt):
    coefficients = []
    rexponents = []
    gexponents = []

    txt = txt.strip()
    for l in txt.splitlines():
        l = l.split()
        rexponents.append(l[0])
        gexponents.append(l[1])
        coefficients.append(l[2:])

    for i in coefficients:
        if len(i) != len(coefficients[0]):
            print(coefficients)
            raise RuntimeError('Different number of general contractions')


    coefficients = list(map(list, zip(*coefficients)))
    return (rexponents,gexponents,coefficients)


def determine_role_region(r):
    orb_roles = ['diffuse', 'polarization', 'rydberg', 'tight', 'valence']

    role = 'orbital'

    region = r
    if r == 'orbital':
        region = 'valence'
    elif r == 'ecporb':
        region = 'valence'

    return (role, region)


def read_basis_xml(xmlfile):
    # File without the extension
    file_base = os.path.splitext(xmlfile)[0]

    # Parse the XML
    bsdict = {}
    root = ET.parse(xmlfile).getroot()

    # Read the metadata
    bsdict['basisSetName'] = get_single_text(root, 'dc:title')

    # Abstract is optional
    abstract = get_single_text(root, 'dct:abstract')
    if not abstract:
        abstract = bsdict['basisSetName']
    bsdict['basisSetDescription'] = abstract

    bstype = get_single_text(root, 'default:basisSetType')
    role, region = determine_role_region(bstype)

    harmonicType = get_single_text(root, 'default:harmonicType')
    functionType = 'gto'

    # Path to the reference file
    ref_file = get_single_link(root, 'default:referencesLink')
    if ref_file:
        ref_base = os.path.splitext(ref_file)[0]

    # Read description and referece data and store in a separate file
    bs_desc = get_single_text(root, 'dc:description')
    if ref_file:
        bs_ref = read_ref_data(ref_file)
    if bs_desc or bs_ref:
        with open(file_base + '.txt', 'w') as f:
            if bs_desc:
                f.write("FROM DESCRIPTION:\n----------------\n")
                f.write(bs_desc)
            if bs_ref:
                f.write("FROM REFERENCE:\n----------------\n")
                f.write(bs_ref)

    # Read in contraction data
    bsdict['basisSetElements'] = {}
    all_contractions = root.findall('default:contractions', ns)

    for cs in all_contractions:
        # Read in element and convert to Z number
        el = cs.attrib['elementType']
        el = bse.lut.element_data_from_sym(el)[1]

        elementData = { 'elementReferences': [ref_base] }
        shells = []

        for c in cs.findall('default:contraction', ns):
            # read in angular momentum, convert to integers
            am = c.attrib['shell']
            am = bse.lut.amchar_to_int(am)

            mat = get_single_node(c, 'cml:matrix')
            nprim = int(mat.attrib['rows'])
            ngen = int(mat.attrib['columns']) - 1  # Columns includes exponents
            exponents,coefficients = text_to_cont(mat.text)

            shell = { 'shellFunctionType': functionType,
                      'shellHarmonicType': harmonicType,
                      'shellRegion' : region,
                      'shellAngularMomentum': am,
                      'shellExponents' : exponents,
                      'shellCoefficients' : coefficients
                     }
            shells.append(shell)

        elementData['elementElectronShells'] = shells
        bsdict['basisSetElements'][el] = elementData

    return bsdict


def read_ecp_xml(xmlfile):
    # File without the extension
    file_base = os.path.splitext(xmlfile)[0]

    # Parse the XML
    bsdict = {}
    root = ET.parse(xmlfile).getroot()

    # Read the metadata
    bsdict['basisSetName'] = get_single_text(root, 'dc:title')

    abstract = get_single_text(root, 'dct:abstract')
    if not abstract:
        abstract = bsdict['basisSetName']
    bsdict['basisSetDescription'] = abstract
    ecptype = get_single_text(root, 'default:ecpType')

    # Path to the reference file
    ref_file = get_single_link(root, 'default:referencesLink')
    if ref_file:
        ref_base = os.path.splitext(ref_file)[0]

    # Read description and referece data and store in a separate file
    bs_desc = get_single_text(root, 'dc:description')
    if ref_file:
        bs_ref = read_ref_data(ref_file)
    if bs_desc or bs_ref:
        with open(file_base + '.txt', 'w') as f:
            if bs_desc:
                f.write("FROM DESCRIPTION:\n----------------\n")
                f.write(bs_desc)
            if bs_ref:
                f.write("FROM REFERENCE:\n----------------\n")
                f.write(bs_ref)

    bsdict['basisSetElements'] = {}
    all_pots = root.findall('default:potentials', ns)

    for cs in all_pots:
        # Read in element and convert to Z number
        el = cs.attrib['elementType']
        el = bse.lut.element_data_from_sym(el)[1]

        nelectrons = int(cs.attrib['numElectronsReplaced'])

        elementData = { 'elementReferences': [ref_base],
                        'elementECPElectrons' : nelectrons
                         }
        potentials = []

        for c in cs.findall('default:potential', ns):
            am = c.attrib['shell']
            am = bse.lut.amchar_to_int(am)

            mat = get_single_node(c, 'cml:matrix')
            nprim = int(mat.attrib['rows'])
            ngen = int(mat.attrib['columns']) - 1  # Columns includes exponents
            rexponents,gexponents,coefficients = text_to_ecpcont(mat.text)

            # Change exponents on R to integers
            rexponents = [ int(x) for x in rexponents ]

            pot = { 'potentialECPType' : ecptype, 
                    'potentialAngularMomentum': am,
                    'potentialRExponents' : rexponents,
                    'potentialGaussianExponents' : gexponents,
                    'potentialCoefficients' : coefficients
                   }
            potentials.append(pot)

        elementData['elementECP'] = potentials
        bsdict['basisSetElements'][el] = elementData

    return bsdict


def read_xml(xmlfile):
    if xmlfile.endswith('-ECP.xml'):
        return read_ecp_xml(xmlfile)
    else:
        return read_basis_xml(xmlfile)


def read_basis_xml_agg(xmlfile):
    # File without the extension
    file_base = os.path.splitext(xmlfile)[0]

    # Parse the XML
    root = ET.parse(xmlfile).getroot()

    # Read the metadata
    name = get_single_text(root, 'dc:title')
    desc = get_single_text(root, 'dct:abstract')
    if not desc:
        desc = name

    bstype = get_single_text(root, 'default:basisSetType')
    role, region = determine_role_region(bstype)


    # Path to the reference file
    ref_file = get_single_link(root, 'default:referencesLink')
    if ref_file:
        ref_base = os.path.splitext(ref_file)[0]

    # Read description and referece data and store in a separate file
    bs_desc = get_single_text(root, 'dc:description')
    bs_ref = None
    if ref_file:
        bs_ref = read_ref_data(ref_file)
    if bs_desc or bs_ref:
        with open(file_base + '.txt', 'w') as f:
            if bs_desc:
                f.write("\n\n")
                f.write("FROM DESCRIPTION:\n----------------\n")
                f.write(bs_desc)
            if bs_ref:
                f.write("\n\n")
                f.write("FROM REFERENCE:\n----------------\n")
                f.write(bs_ref)

    # Read in the components
    # These are the paths to the xml files
    xml_files = []

    if root.findall('default:primaryBasisSetLink', ns):
        xml_files.append(get_single_link(root, 'default:primaryBasisSetLink'))
        xml_files.extend(get_links(root, 'default:basisSetLink'))

    # ECP link
    ecp_file = get_single_link(root, 'default:effectivePotentialsLink')
    if ecp_file:
        xml_files.append(ecp_file) 

    # Convert these paths to json files instead
    # and read in the basis set data
    json_files = [ create_json_filename(p) for p in xml_files ]
    json_data = [ bse.read_json_basis(p) for p in json_files ]

    # Find the intersection for all the elements of the basis sets
    elements = []
    for x in json_data:
        elements.append(list(x['basisSetElements'].keys()))

    element_intersection = set(elements[0]).intersection(*elements[1:])
    element_union = set(elements[0]).union(*elements[1:])

    # "Atom" basis dictionary
    elements = { k: { 'elementComponents': json_files } for k in element_intersection }

    atom_dict = { 'basisSetName': name,
                  'basisSetDescription' : desc,
                  'basisSetElements': elements
                 }

    # Periodic table basis dictionary
    elements = { }
    for e in element_union:
        v = []
        for i,p in enumerate(json_files):
            bs = json_data[i]
            if e in bs['basisSetElements'].keys():
                v.append(json_files[i])

        # Use the atom file with the same name
        # (but only if in the intersection)
        # Otherwise, if there is only one entry, and it exists as an
        # element basis, use that
        if e in element_intersection:
            atom_basis_file = create_json_filename(xmlfile, 'element')
            elements[e] = { 'elementEntry': atom_basis_file }
        elif len(v) == 1 and os.path.isfile(create_json_filename(v[0], 'element')):
            elements[e] = { 'elementEntry': os.path.splitext(v[0])[0] + '.element.json' }

    table_dict = { 'basisSetName': name,
                   'basisSetDescription' : desc,
                   'basisSetElements': elements
                 }

    return (atom_dict, table_dict)


def convert_xml(xmlfile):
    bsdict = read_xml(xmlfile)
    outfile = create_json_filename(xmlfile)
    print("New basis file: ", outfile)

    bsdict['molssi_bse_magic'] = 1
    #print(json.dumps(bsdict, indent=4))
    bse.write_json_basis(outfile, bsdict)


def convert_xml_agg(xmlfile):
    atom_dict, table_dict = read_basis_xml_agg(xmlfile)

    atom_basis_path = create_json_filename(xmlfile, 'element')
    table_basis_path = create_json_filename(xmlfile, 'table')

    print("Atom basis: ", atom_basis_path)
    print("Table basis: ", table_basis_path)

    atom_dict['molssi_bse_magic'] = 1
    table_dict['molssi_bse_magic'] = 1
    table_dict['basisSetRole'] = 'orbital'
    bse.write_json_basis(atom_basis_path, atom_dict)
    bse.write_json_basis(table_basis_path, table_dict)


def get_ecp_file(xmlfile):
    root = ET.parse(xmlfile).getroot()
    return get_single_link(root, 'default:effectivePotentialsLink')


def create_xml_agg(xmlfile):
    # Create from a simple (non-composed) basis
    atom_basis_file = create_json_filename(xmlfile, 'element')
    table_basis_file = create_json_filename(xmlfile, 'table')

    # Needed for the table entry
    atom_basis_file = create_json_filename(xmlfile, 'element')

    json_file = os.path.basename(create_json_filename(xmlfile))

    bs = read_xml(xmlfile)

    # May be none
    ecp_file = get_ecp_file(xmlfile)
    if ecp_file:
        ecp_json = create_json_filename(ecp_file)

    elementlist = list(bs['basisSetElements'].keys())

    atom_elements = { k: { 'elementComponents': [ json_file ] } for k in elementlist }
    table_elements = { k: { 'elementEntry': atom_basis_file } for k in elementlist }

    # Handle elements with ecp
    if ecp_file:
        ecp_data = bse.read_json_basis(ecp_json)
        ecp_elements = list(ecp_data['basisSetElements'].keys())

        for k in ecp_elements:
            if not k in atom_elements:
                atom_elements[k] = { 'elementComponents': [ ecp_json ] }
            else:
                atom_elements[k]['elementComponents'].append(ecp_json)

    # Create the actual dictionaries

    atom_dict = { 'basisSetName': bs['basisSetName'],
                  'basisSetDescription': bs['basisSetDescription'],
                  'basisSetElements': atom_elements
                 }

    table_dict = { 'basisSetName': bs['basisSetName'],
                   'basisSetDescription': bs['basisSetDescription'],
                   'basisSetElements': table_elements
                  }

    atom_dict['molssi_bse_magic'] = 1
    table_dict['molssi_bse_magic'] = 1
    table_dict['basisSetRole'] = 'orbital'
    bse.write_json_basis(atom_basis_file, atom_dict)
    bse.write_json_basis(table_basis_file, table_dict)
