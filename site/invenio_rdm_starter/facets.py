"""Search facets of InvenioRDM Starter."""

from datetime import datetime

from invenio_records_resources.services.records.facets.facets import (
    LabelledFacetMixin,
)
from invenio_search.engine import dsl


class DateHistogramFacet(LabelledFacetMixin, dsl.DateHistogramFacet):
    """Date Range Facet

    facets = {
        'publication_date': DateRangeFacet(
            field='dates',
            interval='year',
            format='yyyy'
        )
    }
    """

    def __init__(self, *args, **kwargs):
        """Show only years with at least 1 document, and at most 10 values."""
        kwargs.setdefault("min_doc_count", 1)
        super().__init__(*args, **kwargs)

    def get_value_filter(self, filter_value):
        """Overriding this function to cast string dates to datetime"""

        for interval_type in ("calendar_interval", "fixed_interval"):
            if interval_type in self._params:
                break
        else:
            interval_type = "interval"

        # dealing with a range
        try:
            if "--" in filter_value:
                start, end = [
                    datetime.strptime(year, "%Y") for year in filter_value.split("--")
                ]
                end = self.DATE_INTERVALS[self._params[interval_type]](end)
            else:
                start = datetime.strptime(filter_value, "%Y")
                end = self.DATE_INTERVALS[self._params[interval_type]](start)
        except ValueError:
            start = 0
            end = 1

        # swap them
        if start > end:
            start, end = end, start

        return dsl.query.Range(
            _expand__to_dot=False,
            **{
                self._params["field"]: {
                    "gte": start,
                    "lt": end,
                }
            },
        )


# InvenioRDM's facets, extended rather than copied, so that the facets a
# release adds arrive with it. The Starter shows publication years as a
# histogram and adds facets for affiliations, funders, author identifiers,
# licenses, related works and references.
