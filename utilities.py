import community
import networkx as nx
import pandas as pd

import psycopg2

# credentials for postgresql database
DB_HOST = '89.145.163.87'
DB_PORT = 5432
DB_USERNAME = 'group11'
DB_PASSWORD = 'tsw2020'
DB_NAME = 'tweets'

CONCEPTS_STOPWORDS = ['coronavirus', 'Coronavirus', 'Corona', 'CoronaVirus', 'do', 'amp', 'Deutschland', 'via', 'tun',
                      'primer', 'un', 'del']


def load_graph_from_files(region, relabel=False):
    """
    Reads two csv files (nodelist_{region}.csv and edgelist_{region}.csv) to build a (directed) graph from that

    :param relabel: whether the graph should be relabel with twitter names
    :param region: the name of the region (part of the csv file's name)
    :return: the (directed) graph, list of nodes (ids) with their labels
    """

    # create empty directed graph
    g = nx.DiGraph()

    # read csv files with nodes (id and label)
    nodes_df = pd.read_csv('nodelist_{}.csv'.format(region))
    nodes_df.set_index('Id')

    # drop duplicates from nodes and always keep first occurrence
    nodes_df.drop_duplicates(subset="Id", inplace=True)

    # add all nodes to graph
    g.add_nodes_from(nodes_df['Id'])

    # load csv file with edges (source, target)
    edges_df = pd.read_csv('edgelist_{}.csv'.format(region))

    # add all edges to graph
    g.add_edges_from([tuple(x) for x in edges_df.to_records(index=False)])

    # if required, use Labels for nodes
    if relabel:
        g = relabel_graph(g, nodes_df)

    # return graph and nodes (contains corresponding labels for node ids)
    return g, nodes_df


def relabel_graph(g, nodes_df):
    """
    Relabels all nodes (referred by ID) to their corresponding name/label

    :param g: the graph
    :param nodes_df: the dataframe with Ids ind Labels (as columns)
    :return: the relabeled graph
    """

    # relabel nodes and return graph
    return nx.relabel_nodes(g, {key: column['Label'] for key, column in
                                nodes_df.set_index('Id').to_dict(orient="index").items()})


def get_communities(g):
    """
    Creates communities for a given graph

    :param g: the graph to analyse communities in
    :return: dict of nodes with corresponding community, list of communities with all their nodes
    """

    # create dict of each node (key) with its community (value)
    partitions = community.best_partition(g.to_undirected())

    # dict of communities with empty lists
    communities = {k: [] for k in partitions.values()}

    # fill all nodes to the corresponding community
    for key, value in partitions.items():
        communities[value].append(key)

    # return dict of nodes and dict of communities
    return partitions, communities


def get_conn():
    """
    Get psycopg2 connection to database

    :return:  database connection
    """

    # create and return db connection with credentials from constants
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USERNAME, password=DB_PASSWORD)


def db_to_pandas(query, conn=None):
    """
    Query database to a Pandas dataframe

    :param conn: a connection to use (if None, a new one is temporarily created)
    :param query: the SQL query
    :return: pandas dataframe
    """

    # if no connection was given, create one
    if conn:
        _con = conn
    else:
        _con = get_conn()

    # open cursor
    cur = _con.cursor()

    # get pandas dataframe from query result
    df = pd.read_sql_query(query, _con)

    # close cursor
    cur.close()

    # don't close connection if it was given
    if not conn:
        _con.close()

    return df


def load_concept_counts(where=None, stopwords=True, limit=None, conn=None):
    """
    Loads all concepts with their count.

    WARNING: this is prone to SQL injections!
    :param where: SQL condition like "tweet_id = 1 AND 1 < 2"
    :param stopwords: whether stopword-concepts should be removed
    :param limit: ony get the top X (DESC ORDER)
    :param conn: database connection
    :return: pandas dataframe
    """

    query = """
    SELECT t->>'surfaceForm' as concept, COUNT(*)
    FROM tweet, jsonb_array_elements(concepts) as t
    WHERE concepts IS NOT NULL
    {}
    {}
    GROUP BY concept
    ORDER BY 2 DESC
    {};
    """.format(
        "AND ({})".format(where) if where is not None else "",
        "AND t->>'surfaceForm' NOT IN ({})".format(','.join("'{0}'".format(w) for w in CONCEPTS_STOPWORDS)) if stopwords else "",
        'LIMIT {}'.format(limit) if limit is not None else "",
    )
    return db_to_pandas(query, conn=conn)
