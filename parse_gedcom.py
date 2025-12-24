from gedcom.parser import Parser

gedcom_parser = Parser()
gedcom_parser.parse_file("family.ged")

root = gedcom_parser.get_root_child_elements()

print(f"Total records: {len(root)}")
