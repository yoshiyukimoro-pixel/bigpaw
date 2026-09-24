-- BIG PAW v1.0 RC production-migration draft (PostgreSQL-oriented)
-- Runtime in this package uses SQLite schema embedded in backend/server.py.
-- Reconcile this file with the selected managed DB before production migration.
create table users (
  id bigserial primary key,
  role varchar(20) not null check (role in ('buyer','breeder','operator')),
  email varchar(255) unique not null,
  password_hash text not null,
  display_name varchar(100) not null,
  phone varchar(30),
  created_at timestamptz not null default now()
);

create table breeders (
  id bigserial primary key,
  user_id bigint unique not null references users(id),
  kennel_name varchar(150) not null,
  prefecture varchar(50) not null,
  animal_business_registration_no varchar(120),
  registration_expires_on date,
  profile text,
  review_status varchar(20) not null default 'pending',
  created_at timestamptz not null default now()
);

create table dogs (
  id bigserial primary key,
  breeder_id bigint not null references breeders(id),
  breed varchar(100) not null,
  sex varchar(10) not null,
  color varchar(100),
  birth_date date,
  price_yen integer not null,
  current_weight_kg numeric(5,2),
  expected_weight_min_kg numeric(5,2),
  expected_weight_max_kg numeric(5,2),
  status varchar(20) not null default 'open',
  description text,
  created_at timestamptz not null default now()
);

create table dog_health_records (
  id bigserial primary key,
  dog_id bigint not null references dogs(id),
  category varchar(50) not null,
  item_name varchar(150) not null,
  result text,
  tested_on date,
  document_url text
);

create table inquiries (
  id bigserial primary key,
  dog_id bigint not null references dogs(id),
  buyer_id bigint not null references users(id),
  breeder_id bigint not null references breeders(id),
  status varchar(30) not null default 'open',
  created_at timestamptz not null default now()
);

create table messages (
  id bigserial primary key,
  inquiry_id bigint not null references inquiries(id),
  sender_user_id bigint not null references users(id),
  body text not null,
  created_at timestamptz not null default now()
);

create table visits (
  id bigserial primary key,
  inquiry_id bigint unique not null references inquiries(id),
  starts_at timestamptz not null,
  status varchar(20) not null default 'proposed',
  face_to_face_confirmed boolean not null default false,
  confirmed_at timestamptz
);

create table deals (
  id bigserial primary key,
  inquiry_id bigint unique not null references inquiries(id),
  dog_id bigint not null references dogs(id),
  buyer_id bigint not null references users(id),
  breeder_id bigint not null references breeders(id),
  total_price_yen integer not null,
  reservation_amount_yen integer default 0,
  status varchar(30) not null default 'negotiating',
  created_at timestamptz not null default now()
);

create table payments (
  id bigserial primary key,
  deal_id bigint not null references deals(id),
  kind varchar(20) not null check (kind in ('reservation','balance','refund')),
  amount_yen integer not null,
  provider varchar(50),
  provider_payment_id varchar(255),
  status varchar(30) not null,
  paid_at timestamptz
);

create table contracts (
  id bigserial primary key,
  deal_id bigint unique not null references deals(id),
  version varchar(40) not null,
  document_url text,
  buyer_signed_at timestamptz,
  breeder_signed_at timestamptz,
  status varchar(30) not null default 'draft'
);

create table pickups (
  id bigserial primary key,
  deal_id bigint unique not null references deals(id),
  scheduled_at timestamptz,
  completed_at timestamptz,
  notes text
);

create table reviews (
  id bigserial primary key,
  deal_id bigint unique not null references deals(id),
  buyer_id bigint not null references users(id),
  breeder_id bigint not null references breeders(id),
  rating smallint not null check (rating between 1 and 5),
  body text not null,
  status varchar(20) not null default 'published',
  created_at timestamptz not null default now()
);

create table favorites (
  user_id bigint not null references users(id),
  dog_id bigint not null references dogs(id),
  created_at timestamptz not null default now(),
  primary key(user_id,dog_id)
);

create table notifications (
  id bigserial primary key,
  user_id bigint not null references users(id),
  kind varchar(50) not null,
  title varchar(200) not null,
  body text,
  read_at timestamptz,
  created_at timestamptz not null default now()
);
