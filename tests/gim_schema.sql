-- Estructura de las tablas de GIM (esquema gimprod) que usa la API de Matriculación.
-- Generado el 2026-09-25 desde diario_20260505 (copia de gimprod) con una consulta de
-- solo lectura sobre pg_catalog: columnas, tipos, NOT NULL, defaults y PRIMARY KEY.
-- Incluye las claves foráneas entre estas 14 tablas; no las que apuntan al resto de GIM,
-- ni índices ni datos.
-- Solo para pruebas: se carga en el Postgres local de docker-compose.test.yml.

DROP SCHEMA IF EXISTS gimprod CASCADE;
CREATE SCHEMA gimprod;

CREATE SEQUENCE gimprod.address_seq START 1000;
CREATE SEQUENCE gimprod.adjunct_seq START 1000;
CREATE SEQUENCE gimprod.entry_seq START 1000;
CREATE SEQUENCE gimprod.entrydefinition_seq START 1000;
CREATE SEQUENCE gimprod.entrystructure_seq START 1000;
CREATE SEQUENCE gimprod.fiscalperiod_seq START 1000;
CREATE SEQUENCE gimprod.item_seq START 1000;
CREATE SEQUENCE gimprod.municipalbond_seq START 1000;
CREATE SEQUENCE gimprod.municipalbondnumber START 1000;
CREATE SEQUENCE gimprod.resident_seq START 1000;
CREATE SEQUENCE gimprod.vehicle_seq START 1000;
CREATE SEQUENCE gimprod.vehiclemaker_seq START 1000;
CREATE SEQUENCE gimprod.vehicletype_seq START 1000;

CREATE TABLE gimprod.address (
    id bigint NOT NULL DEFAULT nextval('gimprod.address_seq'::regclass),
    city character varying(25) NOT NULL,
    country character varying(25) NOT NULL,
    mobilenumber character varying(15),
    neighborhood character varying(60),
    phonenumber character varying(15),
    postalcode character varying(10),
    street character varying(120) NOT NULL,
    resident_id bigint,
    neighborhood2 character varying(180),
    street2 character varying(255),
    parish character varying(30),
    reference character varying(200),
    PRIMARY KEY (id)
);

CREATE TABLE gimprod.adjunct (
    id bigint NOT NULL DEFAULT nextval('gimprod.adjunct_seq'::regclass),
    code character varying,
    PRIMARY KEY (id)
);

CREATE TABLE gimprod.entry (
    id bigint NOT NULL DEFAULT nextval('gimprod.entry_seq'::regclass),
    adjunctclassname character varying(250),
    amountlabel character varying(50),
    code character varying(10),
    creationdate date,
    datepattern character varying(40),
    department character varying(255),
    description character varying(255),
    entrytype character varying(15),
    groupingcodelabel character varying(50),
    hasdirectemission boolean,
    hasmultipleemission boolean,
    isactive boolean,
    isamounteditable boolean,
    istaxable boolean,
    isvalueeditable boolean,
    name character varying(120) NOT NULL,
    previouscode character varying(10),
    reason character varying(255),
    timetocalculate integer,
    account_id bigint,
    entrytypeincome_id bigint,
    receipttype_id bigint,
    timeperiod_id bigint,
    emitoninternal boolean,
    ispreviouspaymentfieldenabled boolean,
    sublineaccount_id bigint,
    completename character varying(250),
    explanatorynote character varying(100),
    iscollectible boolean,
    seniordiscountenabled boolean DEFAULT false,
    bceaccount_id bigint,
    adjunctclassnamegim2 character varying(250),
    PRIMARY KEY (id)
);

CREATE TABLE gimprod.entrydefinition (
    id bigint NOT NULL DEFAULT nextval('gimprod.entrydefinition_seq'::regclass),
    applyinterest boolean,
    entrydefinitiontype character varying(15),
    factor integer,
    isautonullable boolean,
    iscurrent boolean,
    rule text,
    startdate date,
    value numeric(19,2),
    entry_id bigint,
    reason character varying(255),
    rulegim2 text,
    PRIMARY KEY (id)
);

CREATE TABLE gimprod.entrystructure (
    id bigint NOT NULL DEFAULT nextval('gimprod.entrystructure_seq'::regclass),
    entrystructuretype character varying(15),
    _order integer,
    child_id bigint,
    parent_id bigint,
    targetentry_id bigint,
    PRIMARY KEY (id)
);

CREATE TABLE gimprod.fiscalperiod (
    id bigint NOT NULL DEFAULT nextval('gimprod.fiscalperiod_seq'::regclass),
    enddate date NOT NULL,
    name character varying(60) NOT NULL,
    startdate date NOT NULL,
    basicsalary numeric(19,2),
    salariesnumber numeric(19,2),
    mortgagerate numeric(19,2),
    basicsalaryunifiedforrevenue numeric(19,2),
    PRIMARY KEY (id)
);

CREATE TABLE gimprod.item (
    id bigint NOT NULL DEFAULT nextval('gimprod.item_seq'::regclass),
    amount numeric(19,2),
    istaxable boolean,
    observations character varying(255),
    ordernumber integer,
    total numeric(19,2),
    value numeric(19,2),
    discountedbond_id bigint,
    entry_id bigint,
    municipalbond_id bigint,
    surchargedbond_id bigint,
    targetentry_id bigint,
    PRIMARY KEY (id)
);

CREATE TABLE gimprod.municipalbond (
    id bigint NOT NULL DEFAULT nextval('gimprod.municipalbond_seq'::regclass),
    address character varying(255),
    applyinterest boolean,
    balance numeric(19,2),
    base numeric(19,2),
    creationdate date,
    creationtime time without time zone,
    description character varying(500),
    discount numeric(19,2),
    emisiondate date,
    emisionperiod date,
    emisiontime time without time zone,
    exempt boolean,
    expirationdate date,
    groupingcode character varying(100),
    interest numeric(19,2),
    isnopasivesubject boolean,
    legalstatus character varying(10),
    municipalbondtype character varying(15),
    nontaxabletotal numeric(19,2),
    number bigint,
    paidtotal numeric(19,2),
    printingsnumber integer,
    reference character varying(1200),
    servicedate date,
    surcharge numeric(19,2),
    taxabletotal numeric(19,2),
    taxestotal numeric(19,2),
    value numeric(19,2),
    adjunct_id bigint,
    creditnote_id bigint,
    emitter_id bigint,
    entry_id bigint,
    fiscalperiod_id bigint,
    institution_id bigint,
    municipalbondstatus_id bigint,
    notification_id bigint,
    originator_id bigint,
    paymentagreement_id bigint,
    resident_id bigint,
    timeperiod_id bigint,
    emissionorder_id bigint,
    bondaddress character varying(255),
    internaltramit boolean,
    version bigint,
    previouspayment numeric(19,2),
    liquidationdate date,
    liquidationtime time without time zone,
    reverseddate date,
    reversedresolution character varying(255),
    reversedtime time without time zone,
    mbstatusemaalep bigint,
    mbstatusemaalep2014 bigint,
    interestvoucher numeric(19,2),
    surchargevoucher numeric(19,2),
    metadata character varying(255),
    documentisredeemed boolean,
    exchangedate date,
    exchangeobservation character varying(255),
    exchangeuser character varying(255),
    interestcalculationdate timestamp without time zone,
    cempaymentdiscount boolean DEFAULT false,
    forexternalcoactive boolean DEFAULT false,
    additionaldata text,
    channel_id bigint,
    PRIMARY KEY (id)
);

CREATE TABLE gimprod.resident (
    residenttype character varying(1),
    id bigint NOT NULL DEFAULT nextval('gimprod.resident_seq'::regclass),
    email character varying(255),
    identificationnumber character varying(15),
    identificationtype character varying(30),
    isenabledfordeferredpayments boolean,
    name character varying(200),
    registerdate date,
    birthday date,
    country character varying(255),
    firstname character varying(100),
    gender character varying(15),
    handicapednumber character varying(15),
    handicapedpercentage numeric(19,2),
    isdead boolean,
    ishandicaped boolean,
    lastname character varying(100),
    maritalstatus character varying(10),
    code character varying(255),
    constitutiondate date,
    legalentitytype character varying(15),
    currentaddress_id bigint,
    user_id bigint,
    enabledindividualpayment boolean,
    isforeign boolean,
    enablesubscription boolean,
    generateuniqueaccountt boolean,
    origen bigint NOT NULL DEFAULT 68,
    updateddinardap boolean DEFAULT false,
    deathdead date,
    PRIMARY KEY (id)
);

CREATE TABLE gimprod.systemparameter (
    name character varying(255) NOT NULL,
    classname character varying(255) NOT NULL,
    description character varying(255),
    value character varying(2100) NOT NULL,
    PRIMARY KEY (name)
);

CREATE TABLE gimprod.vehicle (
    cubiccentimeters double precision,
    enginenumber character varying(255),
    vin character varying(255),
    weightcapacity double precision,
    year integer,
    id bigint NOT NULL DEFAULT nextval('gimprod.vehicle_seq'::regclass),
    vehiclemaker_id bigint,
    vehicletype_id bigint,
    marca character varying(30),
    tipo character varying(30),
    placa character varying(30),
    licenseplate character varying(255),
    notificationwsresult character varying(255),
    ordernumber character varying(255),
    PRIMARY KEY (id)
);

CREATE TABLE gimprod.vehiclemaker (
    id bigint NOT NULL DEFAULT nextval('gimprod.vehiclemaker_seq'::regclass),
    name character varying(255),
    PRIMARY KEY (id)
);

CREATE TABLE gimprod.vehiclerevisionvalues (
    id bigint NOT NULL,
    revisionnumber character varying(255),
    typevehicle character varying(255),
    valuepercentage numeric(19,2),
    isactive boolean,
    PRIMARY KEY (id)
);

CREATE TABLE gimprod.vehicletype (
    id bigint NOT NULL DEFAULT nextval('gimprod.vehicletype_seq'::regclass),
    name character varying(255),
    PRIMARY KEY (id)
);


-- Claves foráneas que existen en GIM entre estas mismas tablas (mismos nombres).
ALTER TABLE gimprod.address ADD CONSTRAINT fk1ed033d466ae57bb FOREIGN KEY (resident_id) REFERENCES gimprod.resident(id);
ALTER TABLE gimprod.entrydefinition ADD CONSTRAINT fk605e6b45475dc11c FOREIGN KEY (entry_id) REFERENCES gimprod.entry(id);
ALTER TABLE gimprod.entrystructure ADD CONSTRAINT fk1e30714127129c32 FOREIGN KEY (child_id) REFERENCES gimprod.entry(id);
ALTER TABLE gimprod.entrystructure ADD CONSTRAINT fk1e3071413f8f35e4 FOREIGN KEY (parent_id) REFERENCES gimprod.entry(id);
ALTER TABLE gimprod.entrystructure ADD CONSTRAINT fk1e307141e49e11ad FOREIGN KEY (targetentry_id) REFERENCES gimprod.entry(id);
ALTER TABLE gimprod.item ADD CONSTRAINT fk22ef33475dc11c FOREIGN KEY (entry_id) REFERENCES gimprod.entry(id);
ALTER TABLE gimprod.item ADD CONSTRAINT fk22ef3370bfe85c FOREIGN KEY (municipalbond_id) REFERENCES gimprod.municipalbond(id);
ALTER TABLE gimprod.item ADD CONSTRAINT fk22ef33b11afbae FOREIGN KEY (surchargedbond_id) REFERENCES gimprod.municipalbond(id);
ALTER TABLE gimprod.item ADD CONSTRAINT fk22ef33e49e11ad FOREIGN KEY (targetentry_id) REFERENCES gimprod.entry(id);
ALTER TABLE gimprod.item ADD CONSTRAINT fk22ef33f1ca09ee FOREIGN KEY (discountedbond_id) REFERENCES gimprod.municipalbond(id);
ALTER TABLE gimprod.municipalbond ADD CONSTRAINT fk3021acb5475dc11c FOREIGN KEY (entry_id) REFERENCES gimprod.entry(id);
ALTER TABLE gimprod.municipalbond ADD CONSTRAINT fk3021acb566ae57bb FOREIGN KEY (resident_id) REFERENCES gimprod.resident(id);
ALTER TABLE gimprod.municipalbond ADD CONSTRAINT fk3021acb56e7f7a54 FOREIGN KEY (originator_id) REFERENCES gimprod.resident(id);
ALTER TABLE gimprod.municipalbond ADD CONSTRAINT fk3021acb5cb0308fb FOREIGN KEY (fiscalperiod_id) REFERENCES gimprod.fiscalperiod(id);
ALTER TABLE gimprod.municipalbond ADD CONSTRAINT fk3021acb5d2692722 FOREIGN KEY (emitter_id) REFERENCES gimprod.resident(id);
ALTER TABLE gimprod.municipalbond ADD CONSTRAINT fk3021acb5e349bc3c FOREIGN KEY (adjunct_id) REFERENCES gimprod.adjunct(id);
ALTER TABLE gimprod.resident ADD CONSTRAINT fkef29b17021754b52 FOREIGN KEY (currentaddress_id) REFERENCES gimprod.address(id);
ALTER TABLE gimprod.vehicle ADD CONSTRAINT fk779c270c1c91e578 FOREIGN KEY (vehicletype_id) REFERENCES gimprod.vehicletype(id);
ALTER TABLE gimprod.vehicle ADD CONSTRAINT fk779c270c76e68f2e FOREIGN KEY (id) REFERENCES gimprod.adjunct(id);
ALTER TABLE gimprod.vehicle ADD CONSTRAINT fk779c270c9fffa4fc FOREIGN KEY (vehiclemaker_id) REFERENCES gimprod.vehiclemaker(id);
