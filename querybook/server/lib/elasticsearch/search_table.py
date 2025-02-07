from lib.elasticsearch.query_utils import (
    match_filters,
    highlight_fields,
    order_by_fields,
)


def _match_table_word_fields(fields):
    search_fields = []
    for field in fields:
        # 'table_name', 'description', and 'column' are fields used by Table search
        if field == "table_name":
            search_fields.append("full_name^2")
            search_fields.append("full_name_ngram")
        elif field == "description":
            search_fields.append("description")
        elif field == "column":
            search_fields.append("columns")
    return search_fields


def _match_table_phrase_queries(fields, keywords):
    phrase_queries = []
    for field in fields:
        if field == "table_name":
            phrase_queries.append(
                {"match_phrase": {"full_name": {"query": keywords, "boost": 10}}}
            )
        elif field == "column":
            phrase_queries.append({"match_phrase": {"columns": {"query": keywords}}})
    return phrase_queries


def construct_tables_query(
    keywords,
    filters,
    fields,
    limit,
    offset,
    concise,
    sort_key=None,
    sort_order=None,
):
    search_query = {}
    if keywords:
        search_query = {
            "bool": {
                "must": {
                    "multi_match": {
                        "query": keywords,
                        "fields": _match_table_word_fields(fields),
                        # All words must appear in a field
                        "operator": "and",
                    },
                },
                "should": _match_table_phrase_queries(fields, keywords),
            }
        }
    else:
        search_query = {"match_all": {}}

    search_query = {
        "function_score": {
            "query": search_query,
            "boost_mode": "multiply",
            "script_score": {
                "script": {
                    "source": "1 + (doc['importance_score'].value + (doc['golden'].value ? 1 : 0))"
                }
            },
        }
    }

    search_filter = match_filters(filters)

    bool_query = {}
    if search_query != {}:
        bool_query["must"] = [search_query]
    if search_filter != {}:
        bool_query["filter"] = search_filter["filter"]
        if "range" in search_filter:
            bool_query.setdefault("must", [])
            bool_query["must"] += search_filter["range"]

    query = {
        "query": {"bool": bool_query},
        "size": limit,
        "from": offset,
    }

    if concise:
        query["_source"] = ["id", "schema", "name"]

    query.update(order_by_fields(sort_key, sort_order))
    query.update(
        highlight_fields(
            {
                "columns": {
                    "fragment_size": 20,
                    "number_of_fragments": 5,
                },
                "description": {
                    "fragment_size": 60,
                    "number_of_fragments": 3,
                },
            }
        )
    )

    return query
