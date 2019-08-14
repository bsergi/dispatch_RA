# Created on Thu Apr 18 08:46:48 2019
# @author: bsergi

library(ggplot2)
library(openxlsx)
library(plyr)
library(reshape2)

## Working directory and inputs ####
baseWD <- "/Users/Cartographer/GAMS/dispatch_RA-master"
resultsFolder <- "model_runs"

#baseWD <- "C:/Users/llavi/Desktop/research/dispatch_RA-master"
setwd(paste(baseWD, "post_processing", sep="/"))

## Load model results ####

# helper function to read all files in date range of a specific output
readFiles <- function(filename, dates, dateWD, subFolder="results"){
  
  for(i in 1:length(dates)){
    date <- dates[i]
    dateString <- paste(as.numeric(format(date, "%m")), as.numeric(format(date, "%d")), as.numeric(format(date, "%Y")), sep=".")
    
    setwd(paste(dateWD, dateString, subFolder, sep="/"))
    
    # load file
    df <- read.csv(filename)
    df$date <- date
    
    if(i == 1){
      fullDF <- df
    } else{
      fullDF <- rbind(fullDF, df)
    }
  }
  return(fullDF)
}

loadResults <- function(dates, case){
        
  dateMonth <- unique(format(dates, "%b"))  # extract month of dates for directory
  dateYear <- unique(format(dates, "%Y"))  # extract year of dates for directory
  
  if (length(dateMonth) == 1){
    dayStart <- as.numeric(format(dates[1], "%d"))
    dayEnd <- as.numeric(format(dates[length(dates)], "%d"))
    
    # case options: NoReserves, SimpleORDC, ConstantReserves, withORDC
    directory <- paste(dateMonth, dayStart, dayEnd, dateYear, case, sep="_")
    dateResultsWD <- paste(baseWD, resultsFolder, directory, sep="/")
    
  } else{
    print("Error. Multiple months in date range.")   # multiple months yields error for now, can update based on directory format
    return(NULL)
  }
  
  modelLMP <- readFiles("zonal_prices.csv", dates, dateResultsWD)
  txFlows <- readFiles("tx_flows.csv", dates, dateResultsWD)
  reserves <- readFiles("reserve_segment_commit.csv", dates, dateResultsWD)
  dispatch <- readFiles("generator_dispatch.csv", dates, dateResultsWD)
  VRE <- readFiles("renewable_generation.csv", dates, dateResultsWD)
  
  ordc <- readFiles("full_ordc.csv", dates, dateResultsWD, subFolder="inputs")
  gens <- readFiles("PJM_generators_full.csv", dates, dateResultsWD, subFolder="inputs")
  zonalLoad <- readFiles("timepoints_zonal.csv", dates, dateResultsWD, subFolder="inputs")
  
  # some formaating
  gens <- gens[!duplicated(gens),] # remove duplicate generations
  gens <- gens[,c("Name", "Zone", "Category")]  # subset generator columns
  
  # return results
  results <- list(modelLMP, zonalLoad, reserves, ordc, dispatch, VRE, gens, txFlows)
  names(results) <- c("modelLMP", "zonalLoad", "reserves", "ordc", "dispatch", "VRE", "gens", "txFlows")
  return(results)
}

# helper function to load data from all four cases
loadAllCases <- function(dates, cases){
  results <- list()
  for(case in cases){
    results[[case]] <- loadResults(dates, case=case)
  }
  return(results)
}

aggregateCaseData <- function(results, targetData){
  newDF <- data.frame()
  # format results by case
  for(case in names(results)){
    dfTemp <- results[[case]][[targetData]] 
    dfTemp$case <- case
    newDF <- rbind(newDF, dfTemp)
  }
  return(newDF)
}

## LMPs ####

readPJM_LMPs <- function(dates){
  setwd(paste(baseWD, "post_processing", sep="/"))
  reportedLMPs <- read.csv("lmp_historical.csv")

  reportedLMPs$datetime <- as.POSIXct(reportedLMPs[,"Local.Datetime..Hour.Ending."], format="%m/%d/%Y %H:%M")
  #reportedLMPs$datetime <- reportedLMPs$datetime + 1*3600 #get the times in same
  reportedLMPs$date <-format(reportedLMPs$datetime, "%m-%d-%y")
  reportedLMPs$hour <- as.numeric(format(reportedLMPs$datetime, "%H"))
  
  reportedLMPsub <- reportedLMPs[reportedLMPs$date %in% format(dates, "%m-%d-%y"),]
  reportedLMPsub$date <- as.POSIXct(reportedLMPsub$date, format="%m-%d-%y")
  
  return(reportedLMPsub)
}

plotLMPs <- function(results, dates, plotTitle, truncate_value=NA){
  
  modelLMP <- aggregateCaseData(results, "modelLMP")
  
  # zonalLoad is the same across cases (model input)
  zonalLoad <- results[[1]][["zonalLoad"]]
    
  #formatting of model LMP
  colnames(modelLMP)[1] <- "Node"
  
  # add in gross load
  modelLMP <- merge(modelLMP, zonalLoad[,c("date", "timepoint", "zone", "gross_load")], 
                    by.x=c("date", "hour", "Node"), by.y=c("date", "timepoint", "zone"), all=T, sort=F)

  # calculated generation-weighted average across zones for PJM-wide LMP
  PJM_LMP <- ddply(modelLMP, ~ case + date + hour, summarize, 
                   LMP = sum(gross_load * LMP / sum(gross_load)), 
                   gross_load = sum(gross_load))
  PJM_LMP$Node <- "PJM"
  PJM_LMP <- PJM_LMP[,c("date", "hour", "Node", "LMP", "case", "gross_load")]
  modelLMP <- rbind(modelLMP, PJM_LMP)
  modelLMP <- subset(modelLMP, select=-gross_load)
  
  # harmonize zone names and formats for merge
  modelLMP$Node <- mapvalues(modelLMP$Node, from=c("DC_BGE_PEP", "PA_METED_PPL"), to=c("BGE", "PPL"))
  
  # shift hour window and drop any timepoints outside of 24 hour window
  modelLMP$hour <- modelLMP$hour - 1
  modelLMP <- modelLMP[modelLMP$hour < 24,]
  
  # load and format PJM LMPs
  reportedLMPsub <- readPJM_LMPs(dates)
  reportedLMPsub$case <- "reported"
  reportedLMPsub <- reportedLMPsub[, c("date", "hour", "Price.Node.Name", "Price...MWh", "case")]
  colnames(reportedLMPsub) <- c("date", "hour", "Node", "LMP", "case")
  reportedLMPsub$Node <- mapvalues(reportedLMPsub$Node, 
                                   from=c("PJM-RTO ZONE", "DOMINION HUB", "EASTERN HUB", "WESTERN HUB"), 
                                   to=c("PJM", "VA_DOM", "EAST", "WEST"))
  
  # merge reported and modeled data
  fullLMP <- rbind(modelLMP, reportedLMPsub)
  
  fullLMP$datetime <- with(fullLMP, paste(date, hour))
  fullLMP$datetime <- as.POSIXct(fullLMP$datetime, format = "%Y-%m-%d %H")
  
  # plot
  cases <- c("reported", "NoReserves", "ConstantReserves", "SimpleORDC", "withORDC")
  
  LMPplot <- ggplot(data=fullLMP, aes(x=datetime, y=LMP, colour=case, linetype=case)) + 
    facet_wrap(~Node) + geom_line() + theme_classic() + 
    xlab("") + ylab("LMP ($ per MWh)") + 
    guides(colour=guide_legend(title="scenario"),linetype=guide_legend(title="scenario")) + 
    scale_linetype_manual(breaks = cases, values=c(3,2,1,4,5)) +
    scale_colour_manual(breaks = cases, values=c('#4daf4a','#377eb8','#000000','#984ea3','#ff7f00')) +
    theme(text=element_text(size=12),
          axis.text=element_text(size=10))
  
  if(!is.na(truncate_value) & max(fullLMP$LMP) > truncate_value){
    print("passed.")
    LMPplot <- LMPplot + coord_cartesian(ylim = c(0,truncate_value))
  } 
  
  setwd(paste(baseWD, "post_processing", "figures", sep="/"))
  ggsave(paste0("LMPs ", plotTitle, ".png"), width=10, height=6)
  
}

## Reserve pricing ####
summarizeReserves <- function(results, dates, all=F){
  
  reserves <- aggregateCaseData(results, "reserves")
  ordc <- aggregateCaseData(results, "ordc")
  
  # formatting for reserve results
  reserves$segments <- as.numeric(gsub(",.+", "", reserves$X))
  reserves$hour <- as.numeric(gsub(".+,", "", reserves$X))
  reserves$X <- NULL
  
  colnames(ordc)[colnames(ordc) == "timepoint"] <- "hour"
  
  reserves <- merge(reserves, ordc, all=T, by=c("case", "date", "hour","segments")) 
  reserves <- reserves[with(reserves, order(case, date, hour, segments)),]
  
  # subset to 24 hours
  reserves$hour <- reserves$hour - 1
  reserves <- reserves[reserves$hour < 24,]
  
  # find clearing price
  reserves <- ddply(reserves, ~ case + date + hour, transform, 
                    cumulativeReserve = cumsum(MW),
                    cumulativeProcured = cumsum(MW.on.reserve.segment),
                    procured = sum(MW.on.reserve.segment))
  
  reserves$priceFlag <- ifelse(reserves$procured > reserves$cumulativeReserve | reserves$MW.on.reserve.segment == 0, F, T)
  
  reserves$datetime <- with(reserves, paste(date, hour))
  reserves$datetime <- as.POSIXct(reserves$datetime, format = "%Y-%m-%d %H")
  
  procured <- reserves[reserves$priceFlag,]
  procured <- subset(procured, select=-c(cumulativeProcured, cumulativeReserve, priceFlag))
  colnames(procured)[colnames(procured) == "segments"] <- "lastSegment" 
  colnames(procured)[colnames(procured) == "MW"] <- "segmentLengthMW"
  colnames(procured)[colnames(procured) == "procured"] <- "totalReservesProcured"
  
  # if specified, return all segments otherwise just return last segment on ORDC for each hour
  if(all){
    return(reserves)
  } else {
    return(procured)
  }
  
}


## Total reserve and congestion costs ####

calcCongestionCosts <- function(results, dates){
  
  zonalLoad <- aggregateCaseData(results, "zonalLoad")
  txFlows <- aggregateCaseData(results, "txFlows")

  # drop lines with zero flows (not actually an active line)
  txFlows <- txFlows[txFlows$flow..MW. != 0,]
  
  # separate transmission info
  txFlows$from <- gsub("_to.+", "", txFlows$X)
  txFlows$to <- gsub(".+to_", "", txFlows$X)
  txFlows$to <- gsub("-.+", "", txFlows$to)
  txFlows$hour <- as.numeric(gsub(".+-", "", txFlows$X))
  
  txFlows$X <- NULL
  
  # drop extra hours
  txFlows <- txFlows[txFlows$hour <= 24,]
  
  # identify zone that is receiving transmission
  txFlows$zone <- as.factor(ifelse(txFlows$flow..MW. < 0, txFlows$from, txFlows$to))
  
  # match load for receiving zone by hour
  zonalLoadSub <- zonalLoad[,c("case", "date", "timepoint", "zone", "gross_load")]
  colnames(zonalLoadSub)[colnames(zonalLoadSub) == "timepoint"] <- "hour"
  
  txFlows <- merge(txFlows, zonalLoadSub, by=c("case", "date", "hour", "zone"), all.x=T)
  txFlows$hour <- txFlows$hour - 1
  txFlows$datetime <- as.POSIXct(with(txFlows, paste(date, hour)), format = "%Y-%m-%d %H")
  
  # cost of congestion: price x load in receiving zone (using absolute value of congestion price)
  txFlows$congestionCost <- abs(txFlows$congestion.price....MW.) * txFlows$gross_load
  congestion <- ddply(txFlows, ~ case + datetime, summarize, costs = sum(congestionCost))
  
  return(congestion) 
}

plotWeeklyReserveCosts <- function(results, dates, plotTitle){
  
  procuredReserves <- summarizeReserves(results, dates)
  
  # calclate reserve costs
  procuredReserves$costs <- procuredReserves$Price * procuredReserves$totalReservesProcured
  procuredReserves <- procuredReserves[c("case", "datetime", "costs")]
  
  # read in congestion costs
  congestionCosts <- calcCongestionCosts(results, dates)
  
  procuredReserves$costType <- "reserves"
  congestionCosts$costType <- "congestion"
  
  totalCosts <- rbind(procuredReserves, congestionCosts)
  
  totalCostsSum <- ddply(totalCosts, ~ case + costType, summarize, costs=sum(costs))
  
  # add in reserves 
  newRows <- data.frame(case=c("NoReserves", "ConstantReserves"), costType="reserves", costs=0)
  
  totalCostsSum <- rbind(totalCostsSum, newRows)
  
  ggplot(totalCostsSum, aes(x=case, y=costs/1E6, fill=costType)) + geom_bar(stat="identity", position=position_dodge()) + 
    theme_classic() + xlab("") + ylab("million $") + guides(fill=guide_legend(title="")) + 
    theme(legend.position = "top")
  
  setwd(paste(baseWD, "post_processing", "figures", sep="/"))
  ggsave(paste("Reserve costs ", plotTitle, ".png", sep=""))
  
}

## Reserves vs. price over time period ####
plotReserves <- function(results, dates, plotTitle){
  
  reserveSegments <- summarizeReserves(results, dates, all=T)
  procured <- reserveSegments[reserveSegments$priceFlag!=0,]
  
  # scale for secondary price axis
  scale <- max(procured$Price) / max(reserveSegments$cumulativeProcured) 
  
  ggplot(reserveSegments, aes(x=datetime, y=MW.on.reserve.segment, fill=segments)) + geom_bar(stat='identity', size=0) +
    geom_line(data=procured, aes(x=datetime, y=Price/scale ), colour='red') +
    facet_wrap(~case) +
    scale_y_continuous(sec.axis = sec_axis(~.*scale, name="Reserve price ($ per MW)")) + 
    coord_cartesian(ylim=c(0, max(reserveSegments$cumulativeProcured)*1.05)) +
    xlab("") + ylab("Reserves procured (MW)") + 
    guides(fill=guide_legend(title="ORDC\nsegment"),
           shape=guide_legend()) +
    scale_fill_gradient(breaks=rev(c(1:10))) + theme_classic() + 
    theme(text=element_text(size=12),
          axis.text=element_text(size=10))
  
  setwd(paste(baseWD, "post_processing", "figures", sep="/"))
  ggsave(paste0("Reserves ", plotTitle, ".png"), width=10, height=6)
  
}

## Generation dispatch ####

plotDispatch <- function(results, dates, case, plotTitle, hours=24){

  dispatch <- results[[case]][["dispatch"]]
  gens <- results[[case]][["gens"]]
  VRE <- results[[case]][["VRE"]]
  
  # subset dispatch output to single day (include columns for date and case as well)
  dispatch <- dispatch[, c(1:(hours+1), dim(dispatch)[2])]
  
  colnames(dispatch) <- c("id", 0:(hours-1), "date")
  dispatch$zone <- gsub("-[[:print:]]*", "", dispatch[,1])
  dispatch$plant <- gsub("[[:print:]]*-", "", dispatch[,1])
  dispatch[,"id"] <- NULL
  
  dispatch <- melt(dispatch, id.vars=c("date", "zone", "plant"))
  colnames(dispatch) <- c("date", "zone", "plant", "hour", "MW")
  
  # drop rows with zero generation
  #dispatch <- dispatch[dispatch$MW != 0,]
  
  # match with fuel type
  dispatch <- merge(dispatch, gens[,c("Name", "Category")], by.x="plant", by.y="Name", all.x=T)
  
  # summarize by fuel type
  fuelDispatch <- ddply(dispatch, ~ date + hour + zone + Category, summarize, MW = sum(MW))
  fuelDispatch$zone <- factor(fuelDispatch$zone)
  
  # add in renewable gen. and curtailment
  VRE <- melt(VRE, id.vars = c("date", "timepoint", "zone"))
  colnames(VRE) <- c("date", "hour", "zone", "Category", "MW")
  VRE$hour <- factor(VRE$hour - 1)
  
  fuelDispatch <- rbind(fuelDispatch, VRE)
  fuelDispatch$datetime <- as.POSIXct(with(fuelDispatch, paste(date, hour)), format = "%Y-%m-%d %H")
  
  
  fuelDispatch$Category <- factor(fuelDispatch$Category, levels = c("curtailment", "DR", "wind", "solar", "DS", 
                                                                    "CT", "CC", "ST", "NU", "HD", NA))
  #fuelDispatch$Category <- mapvalues()
  # calculate PJM wide
  PJM_dispatch <- ddply(fuelDispatch, ~ datetime + Category, summarize, MW = sum(MW))
  PJM_dispatch$zone <- "All PJM"
  
  fuelDispatch <- fuelDispatch[,c("datetime", "Category", "MW", "zone")]
  fuelDispatch <- rbind(fuelDispatch, PJM_dispatch)
  
  curtailedPower <- fuelDispatch[fuelDispatch$Category == "curtailment" & !is.na(fuelDispatch$Category) & fuelDispatch$MW > 0,]
  
  #fuelDispatch 
  fuelDispatch$Category <- droplevels(fuelDispatch$Category)
  
  ggplot(data=fuelDispatch, aes(x=datetime, y=MW/1E3, fill=Category)) + geom_area() + facet_wrap(~zone, nrow=3, scales = "free") + 
    theme_classic() + ylab("GW") + guides(fill=guide_legend(title="")) + xlab("") +
    scale_x_datetime() +
    ggtitle(paste("Generation by fuel for", plotTitle))
  
  setwd(paste(baseWD, "post_processing", "figures", sep="/"))
  ggsave(paste0("dispatch ", plotTitle, "-", case, ".png"), width=12, height=12)
}

## Price deltas ####

# function to calculate zonal differences 
calcZonalDifference <- function(results, dates, case, zoneMapping){
  
  # load prices 
  actualPrices <- readPJM_LMPs(dates) 
  modelPrices <- results[[case]][["modelLMP"]]

  # actual prices 
  actualPrices <- actualPrices[,c("Price.Node.Name" ,"datetime", "Price...MWh")]
  colnames(actualPrices) <- c("node", "datetime", "price")
  
  actualPrices$node <- mapvalues(actualPrices$node, 
                                 from=c("DOMINION HUB", "EASTERN HUB", "WESTERN HUB", "BGE", "PPL"), 
                                 to=c("VA_DOM", "EAST", "WEST", "DC_BGE_PEP", "PA_METED_PPL"))
  
  # drop PJM wide price
  actualPrices <- actualPrices[actualPrices$node != "PJM-RTO ZONE",]
  
  mapResults <- merge(zoneMapping, actualPrices, by.x="from", by.y="node", all.x=T)
  mapResults <- merge(mapResults, actualPrices, by.x=c("to", "datetime"), by.y=c("node", "datetime"), all.x=T)
  
  # modeled prices 
  modelPrices$hour <- modelPrices$hour - 1   # hours given in 1-24 format, so need to offset to match PJM reported data
  modelPrices <- modelPrices[modelPrices$hour < 24,] # remove extra hours in each (inlcuded to smooth transition between days)
  
  modelPrices$datetime <- as.POSIXct(paste(modelPrices$date, modelPrices$hour), format = "%Y-%m-%d %H")
  colnames(modelPrices)[1] <- "node"
  modelPrices <- modelPrices[,c("node", "datetime", "LMP")]
  
  mapResults <- merge(mapResults, modelPrices, by.x=c("from", "datetime"), by.y=c("node", "datetime"), all.x=T)
  mapResults <- merge(mapResults, modelPrices, by.x=c("to", "datetime"), by.y=c("node", "datetime"), all.x=T)
  
  mapResults <- mapResults[with(mapResults, order(datetime, from, to)),]
  mapResults <- mapResults[,c("datetime", "from", "to", "price.x", "price.y", "LMP.x", "LMP.y")]
  colnames(mapResults) <- c("datetime", "from", "to", "price_actual_from", "price_actual_to", "price_model_from", "price_model_to")
  
  # calculate deltas (from - to)
  mapResults$delta_actual <- mapResults$price_actual_from - mapResults$price_actual_to
  mapResults$delta_model <- mapResults$price_model_from - mapResults$price_model_to
  
  return(mapResults)
}


# function to plot price deltas
plotDeltas <- function(results, dates, txMapping, case, plotTitle){
  
  priceDeltas <- calcZonalDifference(results, dates, case, txMapping)
  
  priceDeltas <- priceDeltas[,c("datetime", "from", "to", "delta_actual", "delta_model")]
  
  priceDeltas <- melt(priceDeltas, id.vars = c("datetime", "from", "to"))
  priceDeltas$interface <- with(priceDeltas, paste(from, "to", to))
  
  ggplot(priceDeltas, aes(x=datetime, y=value, linetype=variable, color=variable)) + geom_line() + 
    facet_wrap(~interface) + xlab("") + ylab("Price differntial ($ per MWh)") +
    guides(linetype=guide_legend(title=""), color=guide_legend(title="")) + #theme_classic() +
    scale_color_manual(breaks = c("delta_actual", "delta_model"), values=c("blue", "red"), labels = c("actual", "model")) +
    scale_linetype_manual(breaks = c("delta_actual", "delta_model"), values=c(1,2), labels = c("actual", "model")) +
    theme(legend.position = "top")
  
  setwd(paste(baseWD, "post_processing", "figures", sep="/"))
  ggsave(paste("Price deltas", plotTitle, "-", case, ".png"), width=8, height=6)
}




## Main ####
dates1 <- seq(as.POSIXct("1/4/2014", format = "%m/%d/%Y"), by="day", length.out=7)
dates2 <- seq(as.POSIXct("10/19/2017", format = "%m/%d/%Y"), by="day", length.out=7)

# cases under consideration
cases <- c("NoReserves", "ConstantReserves", "SimpleORDC", "withORDC")

# load data
results1 <- loadAllCases(dates1, cases=cases)
results2 <- loadAllCases(dates2, cases=cases)

plotLMPs(results1, dates1, plotTitle="Jan 4-10 2014")
plotLMPs(results2, dates2, plotTitle="Oct 19-25 2017")

plotWeeklyReserveCosts(results1, dates1, plotTitle="Jan 4-10 2014")
plotWeeklyReserveCosts(results2, dates2, plotTitle="Oct 19-25 2017")

plotReserves(results1, dates1, plotTitle="Jan 4-10 2014")
plotReserves(results2, dates2, plotTitle="Oct 19-25 2017")

plotDispatch(results1, dates1, case="withORDC", plotTitle="Jan 4-10 2014")
plotDispatch(results2, dates2, case="withORDC", plotTitle="Oct 19-25 2017")

# call price delta functions

# Transmission linkages
# EAST_to_PA_METED_PPL
# WEST_to_DC_BGE_PEP
# WEST_to_VA_DOM
# WEST_to_PA_METED_PPL
# DC_BGE_PEP_to_VA_DOM
# DC_BGE_PEP_to_PA_METED_PPL

txMapping <- data.frame(from=c("EAST", "WEST", "WEST", "WEST", "DC_BGE_PEP", "DC_BGE_PEP"),
                        to=c("PA_METED_PPL", "DC_BGE_PEP", "VA_DOM", "PA_METED_PPL", "VA_DOM", "PA_METED_PPL"))  

plotDeltas(results1, dates1, txMapping, case="withORDC", "Jan 4-10 2014")
plotDeltas(results2, dates2, txMapping, case="withORDC", "Oct 19-25 2017")

## Save ####
setwd(paste(baseWD, "post_processing", sep="/"))
save.image("Results.RData")
