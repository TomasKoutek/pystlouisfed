import logging
from typing import NoReturn
from typing import Optional

from sickle import Sickle
from sickle.iterator import BaseOAIIterator
from sickle.models import Record

logger = logging.getLogger(__name__)


class FRASER:
    """
    | FRASER is a digital library of U.S. economic, financial, and banking history—particularly the history of the Federal Reserve System.

    | Providing economic information and data to the public is an important mission for the St. Louis Fed started by former St. Louis Fed Research Director Homer Jones in 1958.
    | FRASER began as a data preservation and accessibility project of the Federal Reserve Bank of St. Louis in 2004 and now provides access to data and policy documents from the Federal Reserve System and many other institutions.

    https://fraser.stlouisfed.org/
    https://research.stlouisfed.org/docs/api/fraser/
    """

    def __init__(self) -> NoReturn:
        self._sickle = Sickle("https://fraser.stlouisfed.org/oai")

    def list_records(self, ignore_deleted: bool = False, set: Optional[str] = None) -> BaseOAIIterator:
        """
        :type ignore_deleted: bool
        :param set: This parameter specifies the setSpec value and limits the records that are retrieved to only those in the specified set. Ignore this parameter to return all records.
        :type set: str
        :rtype: sickle.iterator.BaseOAIIterator
         
        Description
        -----------
        | https://research.stlouisfed.org/docs/api/fraser/listRecords.html
        | This request returns title records from the FRASER repository.
        | A resumptionToken can be used to retrieve all records using multiple requests.
        | Additional information about an individual title, including the title's child records, can be retrieved using the GetRecord request.

        IGNORE:
        API Request
        -----------
        https://fraser.stlouisfed.org/oai/?verb=ListRecords&metadataPrefix=mods&resumptionToken=1469299598:0
        IGNORE
        
        Example
        -------
        .. code-block:: python
        
            from pystlouisfed import FRASER
            
            for record in FRASER().list_records():
                print(record.get_metadata())

        First record metadata:

        .. code-block:: python

            {
                "name": [None],
                "role": [None],
                "roleTerm": ["creator"],
                "namePart": ["United States. Women's Bureau"],
                "recordInfo": [None, None],
                "recordIdentifier": ["770", "243"],
                "genre": ["government publication"],
                "language": ["eng"],
                "titleInfo": [None, None, None, None],
                "title": [
                    "15 Years After College: A Study of Alumnae of the Class of 1945",
                    "Bulletin of the Women's Bureau",
                    "Bulletin of the Women's Bureau",
                    "Women's Bureau Bulletin"
                ],
                "subTitle": ["Women's Bureau Bulletin, No. 283"],
                "originInfo": [None],
                "place": ["Washington"],
                "issuance": ["monographic"],
                "sortDate": ["1962-01-01"],
                "publisher": ["Govt. Print. Off."],
                "dateIssued": ["1962"],
                "relatedItem": [None],
                "sortOrder": ["b0283"],
                "typeOfResource": ["text"],
                "physicalDescription": [None],
                "form": ["print"],
                "extent": ["32 pages"],
                "digitalOrigin": ["reformatted digital"],
                "internetMediaType": ["application/pdf"],
                "contentType": ["title"],
                "location": [None],
                "url": [
                    "https://fraser.stlouisfed.org/oai/title/15-years-college-a-study-alumnae-class-1945-5549",
                    "https://fraser.stlouisfed.org/images/record-thumbnail.jpg"
                ],
                "accessCondition": [
                    "For more information on rights relating to this item, please see: https://fraser.stlouisfed.org/oai/title/15-years-college-a-study-alumnae-class-1945-5549"
                ]
            }
        """  # noqa

        return self._sickle.ListRecords(metadataPrefix="mods", ignore_deleted=ignore_deleted, set=set)

    def list_sets(self) -> BaseOAIIterator:
        """
        :rtype: sickle.iterator.BaseOAIIterator
        
        Description
        -----------
        | https://research.stlouisfed.org/docs/api/fraser/listSets.html
        | This request returns the set structure for records in the FRASER repository.
        | A resumptionToken can be used to retrieve the complete set structure using multiple requests.

        IGNORE:
        API Request
        -----------
        https://fraser.stlouisfed.org/oai/?verb=ListSets&resumptionToken=1478707638:0
        IGNORE
        
        Example
        -------
        .. code-block:: python
        
            from pystlouisfed import FRASER
            
            for set in FRASER().list_sets():
                print(set)
               
            # <set xmlns="http://www.openarchives.org/OAI/2.0/"><setSpec>author</setSpec><setName>Authors</setName></set>
            # <set xmlns="http://www.openarchives.org/OAI/2.0/"><setSpec>author:1</setSpec><setName>Council of Economic Advisers (U.S.)</setName></set>
            # <set xmlns="http://www.openarchives.org/OAI/2.0/"><setSpec>author:10</setSpec><setName>United States. Federal Open Market Committee</setName></set>
            # <set xmlns="http://www.openarchives.org/OAI/2.0/"><setSpec>author:10064</setSpec><setName>Quarles, Randal Keith, 1957-</setName></set>
            # <set xmlns="http://www.openarchives.org/OAI/2.0/"><setSpec>author:10087</setSpec><setName>Dana, William B. (William Buck), 1829-1910</setName></set>
            # ...
        """  # noqa

        return self._sickle.ListSets()

    def list_identifiers(self, ignore_deleted: bool = False, set: Optional[str] = None) -> BaseOAIIterator:
        """
        :type ignore_deleted: bool
        :param set: :py:class:`str`, This parameter specifies the setSpec value and limits the records that are retrieved to only those in the specified set Ignore this parameter to return all records.
        :type set: str
        :rtype: sickle.iterator.BaseOAIIterator
        
        Description
        -----------
        | https://research.stlouisfed.org/docs/api/fraser/listIdentifiers.htm
        | This request returns headers for records in the FRASER repository.
        | A resumptionToken can be used to retrieve all records using multiple requests.

        IGNORE:
        API Request
        -----------
        https://fraser.stlouisfed.org/oai/?verb=ListIdentifiers&resumptionToken=1469300451:0
        IGNORE
        
        Example
        -------
        .. code-block:: python
        
            from pystlouisfed import FRASER
            
            for header in FRASER().list_identifiers():
                print(header.identifier)
               
            # oai:fraser.stlouisfed.org:title:1
            # oai:fraser.stlouisfed.org:title:7
            # oai:fraser.stlouisfed.org:title:37
            # oai:fraser.stlouisfed.org:title:38
            # oai:fraser.stlouisfed.org:title:39
            # ...
        """  # noqa

        return self._sickle.ListIdentifiers(metadataPrefix="mods", ignore_deleted=ignore_deleted, set=set)

    def get_record(self, identifier: str) -> Record:
        """
        :type identifier: str
        :rtype: sickle.models.Record
        
        Description
        -----------
        | https://research.stlouisfed.org/docs/api/fraser/getRecord.html
        | This request returns a single record from the FRASER repository.

        IGNORE:
        API Request
        -----------
        https://fraser.stlouisfed.org/oai/?verb=GetRecord&identifier=oai:fraser.stlouisfed.org:title:176     
        IGNORE
        
        Example
        -------
        .. code-block:: python
        
            from pystlouisfed import FRASER
            
            record = FRASER().get_record(identifier='oai:fraser.stlouisfed.org:title:176')
            
            print(record)
            
        .. code-block:: xml
            
            <record
                xmlns="http://www.openarchives.org/OAI/2.0/">
                <header>
                    <identifier>oai:fraser.stlouisfed.org:title:176</identifier>
                    <datestamp>2023-12-01T14:55:47Z</datestamp>
                    <setSpec>author:524</setSpec>
                    <setSpec>author:8499</setSpec>
                    <setSpec>subject:4145</setSpec>
                    <setSpec>subject:6824</setSpec>
                    <setSpec>subject:4293</setSpec>
                    <setSpec>theme:8</setSpec>
                    <setSpec>theme:97</setSpec>
                </header>
                <metadata>
                    <mods
                        xmlns="http://www.loc.gov/mods/v3"
                        xmlns:default="http://www.loc.gov/mods/v3" default:xsi="http://www.loc.gov/standards/mods/v3/mods-3-5.xsd" default:schemaLocation="http://www.loc.gov/standards/mods/v3/mods-3-5.xsd">
                        <name>
                            <role>
                                <roleTerm>creator</roleTerm>
                            </role>
                            <namePart>United States. Congress. Senate. Committee on Finance</namePart>
                            <namePart type="date">1815-</namePart>
                            <recordInfo>
                                <recordIdentifier>524</recordIdentifier>
                            </recordInfo>
                        </name>
                        <name>
                            <role>
                                <roleTerm>contributor</roleTerm>
                            </role>
                            <namePart>Seventy-Second Congress</namePart>
                            <namePart type="date">1931-1933</namePart>
                            <recordInfo>
                                <recordIdentifier>8499</recordIdentifier>
                            </recordInfo>
                        </name>
                        <genre>government publication</genre>
                        <subject>
                            <theme>
                                <theme>Great Depression</theme>
                                <recordInfo>
                                    <recordIdentifier>8</recordIdentifier>
                                </recordInfo>
                            </theme>
                            <theme>
                                <theme>Meltzer's History of the Federal Reserve - Primary Sources</theme>
                                <recordInfo>
                                    <recordIdentifier>97</recordIdentifier>
                                </recordInfo>
                            </theme>
                            <topic>
                                <topic>Economic conditions</topic>
                                <recordInfo>
                                    <recordIdentifier>4145</recordIdentifier>
                                </recordInfo>
                            </topic>
                            <topic>
                                <topic>Congressional hearings</topic>
                                <recordInfo>
                                    <recordIdentifier>6824</recordIdentifier>
                                </recordInfo>
                            </topic>
                            <geographic>
                                <geographic>United States</geographic>
                                <recordInfo>
                                    <recordIdentifier>4293</recordIdentifier>
                                </recordInfo>
                            </geographic>
                        </subject>
                        <language>eng</language>
                        <titleInfo>
                            <title>Investigation of Economic Problems</title>
                            <subTitle>Hearings Before the Committee on Finance, United States Senate</subTitle>
                            <titlePartNumber>Seventy-Second Congress, Second Session, Pursuant to S. Res. 315, February 13 to 28, 1933</titlePartNumber>
                        </titleInfo>
                        <identifier type="oclc">4350587</identifier>
                        <originInfo>
                            <place>Washington</place>
                            <issuance>monographic</issuance>
                            <sortDate>1933-02-13</sortDate>
                            <publisher>Government Printing Office</publisher>
                            <dateIssued>February 13-28, 1933</dateIssued>
                        </originInfo>
                        <relatedItem type="series">
                            <titleInfo>
                                <title>Congressional Documents</title>
                            </titleInfo>
                            <recordInfo>
                                <recordIdentifier>5292</recordIdentifier>
                            </recordInfo>
                        </relatedItem>
                        <classification authority="sudocs">Y 4.F 49:Ec 7/</classification>
                        <typeOfResource>text</typeOfResource>
                        <accessCondition>http://rightsstatements.org/vocab/NoC-US/1.0/</accessCondition>
                        <physicalDescription>
                            <form>print</form>
                            <extent>1246 pages</extent>
                            <digitalOrigin>reformatted digital</digitalOrigin>
                            <internetMediaType>application/pdf</internetMediaType>
                        </physicalDescription>
                        <location>
                            <url>https://fraser.stlouisfed.org/oai/title/investigation-economic-problems-176</url>
                            <url access="preview">https://fraser.stlouisfed.org/images/record-thumbnail.jpg</url>
                            <url access="raw object">https://fraser.stlouisfed.org/oai/docs/historical/senate/1933sen_investeconprob/1933sen_investeconprob.pdf</url>
                        </location>
                        <contentType>title</contentType>
                    </mods>
                </metadata>
            </record>

         
        """  # noqa

        return self._sickle.GetRecord(identifier=identifier, metadataPrefix="mods")
