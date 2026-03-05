import streamlit as st
import anthropic
import pandas as pd
import json
from io import StringIO
import networkx as nx
from pyvis.network import Network
import tempfile
import os

st.set_page_config(page_title="NL to SQL Converter", layout="wide")

st.title("🔍 Natural Language to SQL Query Generator")

# Initialize session state
if 'relationships' not in st.session_state:
    st.session_state.relationships = []
if 'schema_dict' not in st.session_state:
    st.session_state.schema_dict = None
if 'tables' not in st.session_state:
    st.session_state.tables = []

# API Key input
api_key = st.sidebar.text_input("Anthropic API Key", type="password", help="Enter your Anthropic API key")

# File upload for schema
st.sidebar.header("📊 Upload Schema Dictionary")
uploaded_file = st.sidebar.file_uploader(
    "Upload table schema (CSV, Excel, or JSON)",
    type=['csv', 'xlsx', 'xls', 'json']
)

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        elif uploaded_file.name.endswith('.json'):
            df = pd.read_json(uploaded_file)
        
        st.sidebar.success(f"✅ Loaded {len(df)} schema entries")
        st.sidebar.dataframe(df.head())
        
        # Convert to schema dictionary format
        st.session_state.schema_dict = df.to_dict('records')
        
        # Extract unique tables
        table_col = 'tablename' if 'tablename' in df.columns else 'table_name'
        st.session_state.tables = sorted(df[table_col].unique().tolist())
        
    except Exception as e:
        st.sidebar.error(f"Error loading file: {str(e)}")

# Tab layout
tab1, tab2, tab3 = st.tabs(["🔗 Table Relationships", "💬 Generate SQL", "📚 Schema View"])

# TAB 1: Table Relationships
with tab1:
    st.header("Define Table Relationships")
    
    if st.session_state.tables:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Add New Relationship")
            
            rel_col1, rel_col2, rel_col3 = st.columns(3)
            
            with rel_col1:
                from_table = st.selectbox("From Table", st.session_state.tables, key="from_table")
            
            with rel_col2:
                to_table = st.selectbox("To Table", st.session_state.tables, key="to_table")
            
            with rel_col3:
                rel_type = st.selectbox("Relationship", ["1:N", "N:1", "1:1", "N:M"], key="rel_type")
            
            # Get columns for selected tables
            if st.session_state.schema_dict:
                from_cols = [entry.get('columnname', entry.get('column_name', '')) 
                           for entry in st.session_state.schema_dict 
                           if entry.get('tablename', entry.get('table_name', '')) == from_table]
                
                to_cols = [entry.get('columnname', entry.get('column_name', '')) 
                          for entry in st.session_state.schema_dict 
                          if entry.get('tablename', entry.get('table_name', '')) == to_table]
                
                col_a, col_b = st.columns(2)
                with col_a:
                    from_column = st.selectbox(f"Column in {from_table}", from_cols, key="from_col")
                with col_b:
                    to_column = st.selectbox(f"Column in {to_table}", to_cols, key="to_col")
                
                if st.button("➕ Add Relationship"):
                    new_rel = {
                        'from_table': from_table,
                        'from_column': from_column,
                        'to_table': to_table,
                        'to_column': to_column,
                        'type': rel_type
                    }
                    st.session_state.relationships.append(new_rel)
                    st.success(f"Added: {from_table}.{from_column} → {to_table}.{to_column} ({rel_type})")
                    st.rerun()
        
        with col2:
            st.subheader("Current Relationships")
            
            if st.session_state.relationships:
                for idx, rel in enumerate(st.session_state.relationships):
                    col_display, col_delete = st.columns([4, 1])
                    with col_display:
                        st.text(f"{rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']} ({rel['type']})")
                    with col_delete:
                        if st.button("🗑️", key=f"delete_{idx}"):
                            st.session_state.relationships.pop(idx)
                            st.rerun()
            else:
                st.info("No relationships defined yet")
        
        # Visualize relationships
        st.subheader("📊 Relationship Graph")
        
        if st.session_state.relationships:
            # Create network graph
            G = nx.DiGraph()
            
            # Add all tables as nodes
            for table in st.session_state.tables:
                G.add_node(table)
            
            # Add relationships as edges
            for rel in st.session_state.relationships:
                label = f"{rel['from_column']}→{rel['to_column']}\n({rel['type']})"
                G.add_edge(rel['from_table'], rel['to_table'], label=label, title=label)
            
            # Create PyVis network
            net = Network(height="500px", width="100%", directed=True, bgcolor="#ffffff")
            net.from_nx(G)
            
            # Customize appearance
            net.set_options("""
            {
                "nodes": {
                    "color": {
                        "border": "#2B7CE9",
                        "background": "#97C2FC",
                        "highlight": {
                            "border": "#2B7CE9",
                            "background": "#D2E5FF"
                        }
                    },
                    "font": {"size": 16},
                    "shape": "box"
                },
                "edges": {
                    "color": {
                        "color": "#848484",
                        "highlight": "#2B7CE9"
                    },
                    "arrows": {
                        "to": {"enabled": true, "scaleFactor": 0.5}
                    },
                    "font": {"size": 12, "align": "middle"},
                    "smooth": {"type": "continuous"}
                },
                "physics": {
                    "enabled": true,
                    "stabilization": {"iterations": 100}
                }
            }
            """)
            
            # Save and display
            with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w') as f:
                net.save_graph(f.name)
                with open(f.name, 'r') as file:
                    html_content = file.read()
                st.components.v1.html(html_content, height=520)
                os.unlink(f.name)
        else:
            st.info("Add relationships above to see the graph visualization")
    else:
        st.warning("Please upload a schema file first in the sidebar")

# TAB 2: Generate SQL
with tab2:
    st.header("Generate SQL Query")
    
    business_question = st.text_area(
        "Enter your business question:",
        placeholder="e.g., Show me total sales by region for the last quarter",
        height=100
    )
    
    col1, col2 = st.columns(2)
    with col1:
        db_dialect = st.selectbox(
            "Select SQL Dialect",
            ["PostgreSQL", "MySQL", "SQL Server", "Oracle", "SQLite", "Snowflake", "BigQuery"]
        )
    
    with col2:
        include_joins = st.checkbox("Auto-generate JOINs based on relationships", value=True)
    
    if st.button("🚀 Generate SQL Query", type="primary"):
        if not api_key:
            st.error("Please enter your Anthropic API key in the sidebar")
        elif not business_question:
            st.error("Please enter a business question")
        else:
            with st.spinner("Generating SQL query..."):
                try:
                    client = anthropic.Anthropic(api_key=api_key)
                    
                    # Build schema context
                    schema_context = ""
                    if st.session_state.schema_dict:
                        schema_context = "\n\nDatabase Schema:\n"
                        for entry in st.session_state.schema_dict:
                            schema_context += f"- Table: {entry.get('tablename', entry.get('table_name', 'N/A'))}\n"
                            schema_context += f"  Column: {entry.get('columnname', entry.get('column_name', 'N/A'))}\n"
                            schema_context += f"  Description: {entry.get('business_description', entry.get('description', 'N/A'))}\n\n"
                    
                    # Add relationship context
                    relationship_context = ""
                    if st.session_state.relationships and include_joins:
                        relationship_context = "\n\nTable Relationships (use these for JOINs):\n"
                        for rel in st.session_state.relationships:
                            relationship_context += f"- {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']} ({rel['type']})\n"
                    
                    prompt = f"""You are a SQL expert. Convert the following business question into a {db_dialect} SQL query.

Business Question: {business_question}
{schema_context}{relationship_context}

Instructions:
- Provide ONLY the SQL query without any explanation
- The query should be valid {db_dialect} syntax
- Use the relationships provided to generate appropriate JOIN statements
- Format the query with proper indentation for readability
"""

                    message = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=1500,
                        messages=[
                            {"role": "user", "content": prompt}
                        ]
                    )
                    
                    sql_query = message.content[0].text.strip()
                    
                    # Remove markdown code blocks if present
                    if sql_query.startswith("```"):
                        sql_query = sql_query.split("```")[1]
                        if sql_query.startswith("sql"):
                            sql_query = sql_query[3:]
                        sql_query = sql_query.strip()
                    
                    st.success("✅ SQL Query Generated!")
                    st.code(sql_query, language="sql")
                    
                    # Copy button
                    st.download_button(
                        label="📋 Download SQL Query",
                        data=sql_query,
                        file_name="query.sql",
                        mime="text/plain"
                    )
                    
                except Exception as e:
                    st.error(f"Error generating query: {str(e)}")

# TAB 3: Schema View
with tab3:
    st.header("Schema Overview")
    
    if st.session_state.schema_dict:
        # Group by table
        df = pd.DataFrame(st.session_state.schema_dict)
        table_col = 'tablename' if 'tablename' in df.columns else 'table_name'
        
        for table in st.session_state.tables:
            with st.expander(f"📋 {table}", expanded=False):
                table_data = df[df[table_col] == table]
                st.dataframe(table_data, use_container_width=True)
    else:
        st.info("Upload a schema file to view the schema details")

# Instructions
with st.expander("ℹ️ How to use"):
    st.markdown("""
    ### Setup
    1. **Get API Key**: Sign up at https://console.anthropic.com and get your API key
    2. **Upload Schema**: Upload a CSV, Excel, or JSON file with columns:
       - `tablename` or `table_name`
       - `columnname` or `column_name`
       - `business_description` or `description`
    
    ### Define Relationships
    1. Go to the **Table Relationships** tab
    2. Select tables and columns to define relationships
    3. Choose relationship type (1:N, N:1, 1:1, N:M)
    4. View the interactive graph showing all connections
    5. Edit or delete relationships as needed
    
    ### Generate SQL
    1. Go to the **Generate SQL** tab
    2. Enter your business question in natural language
    3. Select your database dialect
    4. Enable "Auto-generate JOINs" to use your defined relationships
    5. Click Generate to get your SQL query
    
    ### Schema View
    - View all tables and their columns in an organized format
    """)
