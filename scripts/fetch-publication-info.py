#!/usr/bin/env python3
import argparse
import logging
import requests
import json
import xml.etree.ElementTree as ET


def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description='description',
                                     formatter_class=
                                     argparse.RawTextHelpFormatter)
    parser.add_argument('--input', '-i', type=str, required=True,
                        help='Location of input file')
    parser.add_argument('--output', '-o', type=str,
                        help='Location of output file')
    parser.add_argument('--config', '-c', required=True,
                        help='Config file, see example '
                             'formatting in conf directory')

    args = parser.parse_args()

    # Get SCOPUS API Key
    credentials = json.load(open(args.config, 'r'))
    scopus_key = credentials['scopus']

    # Open file
    input_file = open(args.input, 'r')
    id_list = []

    for line in input_file:
        if line.rstrip() == "pmid":
            pass
        else:
            id_list.append(line.rstrip())

    input_file.close()

    scopus_info = fetch_scopus_info(id_list, scopus_key)
    efetch_info = fetch_efetch_info(id_list)

    # Write to output file or stdout
    headers = ["PMID", "Journal Name", "Journal Pub Date", "Electronic Date", "Citations",
               "Publisher", "Funding Support", "Study Type", "MeSH Terms"]
    header = "\t".join(headers)

    if args.output:
        output = open(args.output, 'w')
        output.write(header + "\n")
    else:
        print(header)

    for pubmed_id in id_list:
        if pubmed_id not in scopus_info:
            scopus_info[pubmed_id] = ""

        row = pubmed_id, efetch_info[pubmed_id][0],\
              efetch_info[pubmed_id][1], efetch_info[pubmed_id][2],\
              scopus_info[pubmed_id], "", "", "" , efetch_info[pubmed_id][3]

        line = "\t".join(row)
        if args.output:
            output.write(line + "\n")
        else:
            print(line)

    return


def fetch_scopus_info(id_list, api_key):
    """
    Fetch citation counts from scopus

    :param id_list: list of pubemed IDs
    :param api_key: scopus api key
    :return: dict where pubmed ids are keys
    and their values are tuples in the order:
    title, journal_date, electronic_date, mesh_terms
    """
    scopus_info = {}

    # split list into chunks of 50 ids
    # see http://stackoverflow.com/a/312464
    chunked_list = [id_list[i:i+50] for i in range(0, len(id_list), 50)]


    SCOPUS_BASE = "https://api.elsevier.com/content/search/scopus"
    params = {
        "apiKey": api_key,
        "field": "citedby-count,pubmed-id",
        "httpAccept": "application/json",
        "count": "50"
    }

    for chunk in chunked_list:
        query = "PMID("
        query += " OR ".join(chunk)
        query += ")"
        params["query"] = query

        scopus_request = requests.get(SCOPUS_BASE, params=params)
        response = scopus_request.json()
        results = response["search-results"]["entry"]

        for result in results:
            scopus_info[result["pubmed-id"]] = result["citedby-count"]

    return scopus_info


def fetch_efetch_info(id_list):
    """
    Fetch publication info from Eutils EFetch

    :param id_list: list of pubmed IDs
    :return: dict where pubmed ids are keys
    and their values are tuples in the order:
    title, journal_date, electronic_date, mesh_terms
    """
    efetch_info = {}
    EFETCH_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {
        "id": id_list,
        "db": "pubmed",
        "retmode": "xml",
        "rettype": "abstract"
    }

    efetch_request = requests.post(EFETCH_BASE, data=params)
    root = ET.fromstring(efetch_request.content)

    for article in root.findall("PubmedArticle"):
        medline = article.find("MedlineCitation")
        pubmed = medline.find("PMID").text
        article = medline.find("Article")
        title = article.find("Journal").find("Title").text


        # Get Dates
        try:
            year = article.find("Journal").find("JournalIssue")\
                          .find("PubDate").find("Year").text
            month = article.find("Journal")\
                           .find("JournalIssue").find("PubDate").find("Month").text
            day = article.find("Journal")\
                         .find("JournalIssue").find("PubDate").find("Day").text
            journal_date = "{0} {1} {2}".format(year, month, day)
        except AttributeError:
            journal_date = ""

        # Get eletronic publication date
        try:
            year = article.find("ArticleDate").find("Year").text
            month = article.find("ArticleDate").find("Month").text
            day = article.find("ArticleDate").find("Day").text
            electronic_date = "{0}/{1}/{2}".format(year, month, day)
        except AttributeError:
            electronic_date = ""

        # Get MeSH terms list
        try:
            mesh_list = []
            MeshHeadings = medline.find("MeshHeadingList").findall("MeshHeading")
            for headings in MeshHeadings:
                mesh_ids = [child.get("UI") for child in headings]
                mesh_group = ";".join(mesh_ids)
                mesh_list.append(mesh_group)
            mesh_terms = "|".join(mesh_list)
        except AttributeError:
            mesh_terms = ""

        efetch_info[pubmed] = title, journal_date, electronic_date, mesh_terms

    return efetch_info


if __name__ == "__main__":
    main()