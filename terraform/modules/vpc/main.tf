# modules/vpc/main.tf

# 1. Main Virtual Private Cloud (VPC)
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.environment}-${var.project_name}-vpc"
    Environment = var.environment
    Project     = var.project_name
  }
}

# 2. Internet Gateway for Public Routing
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name        = "${var.environment}-${var.project_name}-igw"
    Environment = var.environment
  }
}

# 3. Public Subnets (for NAT Gateway / ALBs)
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name        = "${var.environment}-${var.project_name}-public-subnet-${count.index + 1}"
    Environment = var.environment
    Type        = "Public"
  }
}

# 4. Private Subnets (for Lambda Functions & Backend compute)
resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 4)
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name        = "${var.environment}-${var.project_name}-private-lambda-${count.index + 1}"
    Environment = var.environment
    Type        = "PrivateCompute"
  }
}

# 5. Isolated Database Subnets (for RDS PostgreSQL)
resource "aws_subnet" "database" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 8)
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name        = "${var.environment}-${var.project_name}-db-subnet-${count.index + 1}"
    Environment = var.environment
    Type        = "PrivateDatabase"
  }
}

# 6. Database Subnet Group for RDS
resource "aws_db_subnet_group" "db_subnet_group" {
  name        = "${var.environment}-${var.project_name}-db-subnet-group"
  description = "Subnet group for RDS PostgreSQL instances"
  subnet_ids  = aws_subnet.database[*].id

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# 7. Route Tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name        = "${var.environment}-${var.project_name}-public-rt"
    Environment = var.environment
  }
}

resource "aws_route_table_association" "public" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name        = "${var.environment}-${var.project_name}-private-rt"
    Environment = var.environment
  }
}

resource "aws_route_table_association" "private" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "database" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.database[count.index].id
  route_table_id = aws_route_table.private.id
}
