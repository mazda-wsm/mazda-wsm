from markdown import markdown

from mdconverter import TableConverter

# FILENAME = "D933-1A-22C_Ver26/esicont/srvc/html/id075000800100.html"
# FILENAME = "D933-1A-22C_Ver26/esicont/mission/B30/html/id000000810000.html"
# FILENAME = "D933-1A-22C_Ver26/esicont/srvc/html/id031100100200.html"
FILENAME = "D933-1A-22C_Ver26/esicont/srvc/html/id051400255600.html"

TEST_HTML_TABLE = """
<table align="center" height="100%">
    <tr>
        <td valign="top">
            <table align="center" cellspacing="5">
                <tr>
                    <td>
                        <div align="center"
                             style="border: 1px #3C3D44 solid; background-color:#B3B5BE; padding:1px; width:150px;">
                            <a href="../pdf/elwiring.pdf"><font color="#333333" size="2">View</font></a>
                        </div>
                    </td>
                </tr>
            </table>
        </td>
    </tr>
</table>
"""

TEST_TABLE = """
+-------------------------------------------------------------------------------------------------------------------+-----------------------+
| **Item**                                                                                                          | **Specification**     |
+===================================================================================================================+=======================+
| **REFRIGERANT SYSTEM**                                                                                                                    |
+------------------------+------------------------------------------------------------------------------------------+-----------------------+
| Refrigerant            | Type                                                                                     | R-134a                |
+------------------------+-----------------------------------------------------------------------+------------------+-----------------------+
|                        | Regular amount (approx. quantity)                                     | (g {oz})         | 450 {15.9}            |
+------------------------+-----------------------------------------------------------------------+------------------+-----------------------+
| **BASIC SYSTEM**                                                                                                                          |
+------------------------+-----------------------------------+------------------------------------------------------+-----------------------+
| A/C compressor         | Lubrication oil                   | Type                                                 | DH-PR                 |
+------------------------+-----------------------------------+-----------------------------------+------------------+-----------------------+
|                        |                                   | Sealed volume  (approx. quantity) | (ml {cc, fl oz}) | 130 {130, 4.39}       |
+------------------------+-----------------------------------+-----------------------------------+------------------+-----------------------+
| **CONTROL SYSTEM**                                                                                                                        |
+------------------------+-----------------------------------------------------------------------+------------------+-----------------------+
| A/C compressor         | Magnetic clutch clearance                                             | (mm {in})        | 0.3-0.6 {0.012-0.023} |
+------------------------+-----------------------------------------------------------------------+------------------+-----------------------+
"""

if __name__ == '__main__':
    html = markdown(TEST_TABLE, extensions=['grids', 'attr_list', 'def_list', 'sane_lists'])

    tc = TableConverter(keep_inline_images_in=['td'])
    print(tc.convert(open(FILENAME, 'rt').read()))
    print(tc.convert(TEST_HTML_TABLE))