/* Substitute a set of substrings within a larger string.
   When several strings match, the longest wins.
   Similar to php's strtr(string $str, array $replace_pairs).
   Example:
   select multi_replace('foo and bar is not foobar',
             '{"bar":"foo", "foo":"bar", "foobar":"foobar"}'::jsonb);
   => 'bar and foo is not foobar'
 */
CREATE OR REPLACE FUNCTION multi_replace(str text, substitutions jsonb)
RETURNS text
as $$
DECLARE
	regex text;
	s_left text;
	s_tail text;
	res text:='';
BEGIN
	-- collect all keys as a pipe-separated string to insert into the regex to 
	--	match any of the keys in the substitution dict
	-- i.e., key1 | key2 | key 3 ...
	select string_agg(quote_ident(term), '|' )
	from jsonb_object_keys(substitutions) as x(term)
		where term <> ''
	into regex;

	-- the regex doesn't work on a null value, so set it to an empty string
	if (coalesce(regex, '') = '') then
		return str;
	end if;

	-- construct the regex
	regex := concat('^(.*?)(', regex, ')([^_]+.*)$'); -- match no more than 1 row   

	loop
		s_tail := str;
		select 
		   concat(matches[1], substitutions->>matches[2]),
		   matches[3]
		from
		 	regexp_matches(str, regex, 'g') as matches
		into s_left, str;

		exit when s_left is null;
		res := res || s_left;

	end loop;

	res := res || s_tail;
	return res;

END 
$$ LANGUAGE plpgsql strict immutable;

-- keep function to copy views separate so that it can be called on its own
CREATE OR REPLACE FUNCTION clone_views(
	source_schema text,
	dest_schema text
) RETURNS void AS 
$BODY$

	DECLARE
		view_name text;
		record_   record;

	BEGIN

	FOR record_ IN 
		WITH 
		  dict_query AS (
		    SELECT 
		      'a' AS a, 
		      ('{"'|| string_agg(table_name || '": "dev.' || table_name, '","') || '"}')::jsonb AS replace_dict 
		    FROM information_schema.tables 
		    WHERE table_schema='public' 
		    GROUP BY a
		  ), 
		  dependency AS (
		    SELECT
		      source_table.relname as source_table,
		      dependent_view.relname as dependent_views
		    FROM pg_depend 
		    JOIN pg_rewrite ON pg_depend.objid = pg_rewrite.oid 
		    JOIN pg_class as dependent_view ON pg_rewrite.ev_class = dependent_view.oid 
		    JOIN pg_class as source_table ON pg_depend.refobjid = source_table.oid 
		    JOIN pg_namespace source_ns ON source_ns.oid = source_table.relnamespace
		    WHERE 
		      source_ns.nspname = 'public' AND 
		      source_table.relname LIKE '%view' AND
		      source_table.relname <> dependent_view.relname
		  )
		SELECT DISTINCT ON (sort_order, table_name) 
			* 
		FROM (
		  SELECT 
		    table_name,
		    dependency.dependent_views,
		    CASE 
		      WHEN table_name IN (dependency.source_table) AND table_name NOT IN (SELECT dependent_views FROM dependency) THEN 0
		      WHEN table_name IN (dependency.source_table) AND table_name IN (SELECT dependent_views FROM dependency) THEN 1
		      ELSE 2 
		    END AS sort_order,
		    multi_replace(view_definition, replace_dict) AS view_def
		  FROM information_schema.views 
		    JOIN dict_query ON replace_dict::text <> table_name
		    LEFT JOIN dependency ON dependency.source_table = table_name
		  WHERE table_schema = 'public'
		) _
		ORDER BY sort_order, table_name
	LOOP
		view_name := dest_schema || '.' || quote_ident(record_.table_name);
		EXECUTE 'CREATE OR REPLACE VIEW ' || view_name || ' AS ' || record_.view_def || ';' ;
	END LOOP;
  
	RETURN; 
 
	END;

$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;

-- copy schema to dev
CREATE OR REPLACE FUNCTION clone_schema(
    source_schema text,
    dest_schema text,
    include_records boolean)
  RETURNS void AS
$BODY$

--  This function will clone all sequences, tables, data, views & functions from any existing schema to a new one
-- SAMPLE CALL:
-- SELECT clone_schema('public', 'new_schema', TRUE);

DECLARE
  src_oid          oid;
  tbl_oid          oid;
  func_oid         oid;
  object           text;
  buffer           text;
  srctbl           text;
  default_         text;
  column_          text;
  record_          record;
  qry              text;
  dest_qry         text;
  v_def            text;
  seqval           bigint;
  sq_last_value    bigint;
  sq_maximum_value     bigint;
  sq_start_value   bigint;
  sq_increment_by  bigint;
  sq_min_value     bigint;
  sq_cache_value   bigint;
  sq_log_cnt       bigint;
  sq_is_called     boolean;
  sq_is_cycled     boolean;
  sq_cycled        char(10);

BEGIN

-- Check that source_schema exists
  SELECT oid INTO src_oid
    FROM pg_namespace
   WHERE nspname = quote_ident(source_schema);
  IF NOT FOUND
    THEN 
    RAISE NOTICE 'source schema % does not exist!', source_schema;
    RETURN ;
  END IF;

  -- Check that dest_schema does not yet exist
  PERFORM nspname 
    FROM pg_namespace
   WHERE nspname = quote_ident(dest_schema);
  IF FOUND
    THEN 
    RAISE NOTICE 'dest schema % already exists!', dest_schema;
    RETURN ;
  END IF;

  EXECUTE 'CREATE SCHEMA IF NOT EXISTS ' || quote_ident(dest_schema) ;

  -- Create sequences
  -- TODO: Find a way to make this sequence's owner is the correct table.
  FOR object IN
    SELECT sequence_name::text 
      FROM information_schema.sequences
     WHERE sequence_schema = quote_ident(source_schema)
  LOOP
    RAISE NOTICE 'SEQUENCE: %', quote_ident(dest_schema) || '.' || quote_ident(object);
    
    EXECUTE 'CREATE SEQUENCE ' || quote_ident(dest_schema) || '.' || quote_ident(object);
    srctbl := quote_ident(source_schema) || '.' || quote_ident(object);

    EXECUTE 'SELECT last_value, maximum_value, start_value, increment, minimum_value, cache_value, log_cnt, is_cycled, is_called 
              FROM ' || --' || quote_ident(source_schema) || '.' || quote_ident(object) || ';' 
              '(SELECT *, ''a'' AS join_field FROM information_schema.sequences WHERE sequence_schema = ''' || quote_ident(source_schema) || ''' AND sequence_name = ''' || quote_ident(object) || ''') _ NATURAL JOIN (SELECT ''a'' AS join_field, * FROM ' || quote_ident(source_schema) || '.' || quote_ident(object) || ') __ NATURAL JOIN (SELECT ''a'' AS join_field, seqcache AS cache_value, seqcycle AS is_cycled FROM pg_sequence where seqrelid = ''' || quote_ident(object) || '''::regclass) ___ ;'
              INTO sq_last_value, sq_maximum_value, sq_start_value, sq_increment_by, sq_min_value, sq_cache_value, sq_log_cnt, sq_is_cycled, sq_is_called ; 

    IF sq_is_cycled 
      THEN 
        sq_cycled := 'CYCLE';
    ELSE
        sq_cycled := 'NO CYCLE';
    END IF;

    EXECUTE 'ALTER SEQUENCE '   || quote_ident(dest_schema) || '.' || quote_ident(object) 
            || ' INCREMENT BY ' || sq_increment_by
            || ' MINVALUE '     || sq_min_value 
            || ' MAXVALUE '     || sq_maximum_value
            || ' START WITH '   || sq_start_value
            || ' RESTART '      || sq_min_value 
            || ' CACHE '        || sq_cache_value 
            || sq_cycled || ' ;' ;

    buffer := quote_ident(dest_schema) || '.' || quote_ident(object);
    IF include_records 
        THEN
            EXECUTE 'SELECT setval( ''' || buffer || ''', ' || sq_last_value || ', ' || sq_is_called || ');' ; 
    ELSE
            EXECUTE 'SELECT setval( ''' || buffer || ''', ' || sq_start_value || ', ' || sq_is_called || ');' ;
    END IF;

  END LOOP;

-- Create tables 
  FOR object IN
    SELECT table_name::text 
      FROM information_schema.tables 
     WHERE 
        table_schema = quote_ident(source_schema) AND
        table_type = 'BASE TABLE' AND 
        to_regclass(table_name) IS NOT NULL
  LOOP
    buffer := dest_schema || '.' || quote_ident(object);
    EXECUTE 'CREATE TABLE ' || buffer || ' (LIKE ' || quote_ident(source_schema) || '.' || quote_ident(object) 
        || ' INCLUDING ALL)';

    IF include_records 
      THEN 
      -- Insert records from source table
      EXECUTE 'INSERT INTO ' || buffer || ' SELECT * FROM ' || quote_ident(source_schema) || '.' || quote_ident(object) || ';';
    END IF;
 
    FOR column_, default_ IN
      SELECT column_name::text, 
             REPLACE(column_default::text, source_schema, dest_schema) 
        FROM information_schema.COLUMNS 
       WHERE table_schema = dest_schema 
         AND TABLE_NAME = object 
         AND column_default LIKE 'nextval(%' || quote_ident(source_schema) || '%::regclass)'
    LOOP
      EXECUTE 'ALTER TABLE ' || buffer || ' ALTER COLUMN ' || column_ || ' SET DEFAULT ' || default_;
    END LOOP;

  END LOOP;

--  add FK constraint
  FOR qry IN
    SELECT 'ALTER TABLE ' || quote_ident(dest_schema) || '.' || quote_ident(rn.relname) 
                          || ' ADD CONSTRAINT ' || quote_ident(ct.conname) || ' ' || pg_get_constraintdef(ct.oid) || ';'
      FROM pg_constraint ct
      JOIN pg_class rn ON rn.oid = ct.conrelid
     WHERE connamespace = src_oid
       AND rn.relkind = 'r'
       AND ct.contype = 'f'
         
    LOOP
      EXECUTE qry;

    END LOOP;

  -- Make sure destination schema tables point to destination lookup tables
  FOR qry IN
    SELECT 
        format(
            'ALTER TABLE %1$s DROP CONSTRAINT %2$s; ALTER TABLE %1$s ADD CONSTRAINT %2$s %3$s;', 
            pgc.conrelid::regclass::text, 
            constraint_name,  
            replace(pg_get_constraintdef(pgc.oid), pgc.confrelid::regclass::text, dest_schema || '.' || pgc.confrelid::regclass::text)
        ) 
    FROM 
        pg_constraint pgc 
    JOIN information_schema.constraint_column_usage ccu ON conname=constraint_name 
    WHERE 
        constraint_schema <> table_schema AND 
        constraint_schema=dest_schema AND 
        conrelid::regclass::text LIKE dest_schema || '.%'
    
    LOOP
        EXECUTE qry;
    END LOOP;

-- Create views 
  clone_views(source_schema, dest_schema);

-- Create functions 
  FOR func_oid IN
    SELECT oid
      FROM pg_proc 
     WHERE pronamespace = src_oid

  LOOP      
    SELECT pg_get_functiondef(func_oid) INTO qry;
    SELECT replace(qry, source_schema, dest_schema) INTO dest_qry;
    EXECUTE dest_qry;

  END LOOP;
  
  RETURN; 
 
END;
 
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;

ALTER FUNCTION clone_schema(text, text, boolean)
  OWNER TO postgres;


-- create a convenience function for granting permissions after re-creating 
--	schemas or views
CREATE OR REPLACE FUNCTION grant_permissions() 
	RETURNS void AS
$BODY$
	BEGIN
		GRANT USAGE ON SCHEMA public TO :read_role;
		GRANT SELECT ON ALL TABLES IN SCHEMA public TO :read_role;
		GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO :read_role;
		GRANT USAGE ON SCHEMA public TO :write_role;
		GRANT ALL ON ALL TABLES IN SCHEMA public TO :write_role;
		GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO :write_role;

		GRANT USAGE ON SCHEMA dev TO :read_role;
		GRANT SELECT ON ALL TABLES IN SCHEMA dev TO :read_role;
		GRANT SELECT ON ALL SEQUENCES IN SCHEMA dev TO :read_role;
		GRANT USAGE ON SCHEMA dev TO :write_role;
		GRANT ALL ON ALL TABLES IN SCHEMA dev TO :write_role;
		GRANT ALL ON ALL SEQUENCES IN SCHEMA dev TO :write_role;
	END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;

--SELECT clone_views('public', 'dev'), grant_permissions();
SELECT clone_schema('public', 'dev', true), grant_permissions();