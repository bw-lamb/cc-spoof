import { Document, ObjectId, Decimal128 } from 'mongodb';

interface Cardholder extends Document {
	_id?: ObjectId,
	name: {
		first: string,
		last: string
	},
	billingAddress: string
	shippingAddress: string
};

interface Account extends Document {
	_id?: ObjectId,
	accountId: bigint,
	currentBalance: Decimal128,
	creditLimit: Decimal128,
	creationDate: Date,
	cardholders: Cardholder[]
};

type DigitTuple = [number, number, number, number];
type CardStatus = "ACTIVE" | "SUSPENDED" | "COMNPROMISED" | "EXPIRED" | "REPLACED";

interface Card extends Document {
	_id?: ObjectId,
	accountId: bigint,
	cardholder: Cardholder,
	vaultToken: bigint,
	lastFourDigits: DigitTuple,
	status: CardStatus,
	startDate: Date,
	endDate: Date,
	activationDate: Date
};


interface Merchant extends Document {
	_id?: ObjectId,
	merchantId: bigint,
	name: string,
	mccCode: DigitTuple,
	creationDate: Date
};

interface MerchantLocation extends Document {
	_id?: ObjectId,
	merchantId: bigint,
	address: string,
	locationName: string,
	postalCode: string,
	countryCode: string,
	isActive: boolean
};

type TransactionType = "PURCHASE" | "FEE" | "PAYMENT" | "REFUND" | "ADVANCE" | "ADJUSTMENT";

interface Transaction extends Document {
	_id?: ObjectId,
	accountId: bigint,
	transactionId: bigint,
	transactionType: TransactionType,
	transactionDate: Date,
	postedDate: Date,
	amount: Decimal128,
	isDisputed: boolean
};

type AuthCode = [number, number, number, number, number, number];

interface TransactionPurchase extends Transaction {
	merchantId: bigint,
	terminalId: bigint,
	authCode: AuthCode,
	isRecurring: boolean
};

interface TransactionFee extends Transaction {};

interface TransactionPayment extends Transaction {
	method: string,
	routingNumber: number,
	accountNumber: number
};

interface TransactionRefund extends Transaction {
	originalPurchaseId: bigint,
	merchantId: bigint,
	isChargebackDisputed: boolean
};

interface TransactionAdvance extends Transaction {
	atmId: bigint,
	feeApplied: string
};

type AdjustmentDirection = "D" | "C";

interface TransactionAdjustment extends Transaction {
	reason: string,
	authorizedByEmployee: boolean,
	impactDirection: AdjustmentDirection
};