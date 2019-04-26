# Created on Thu Apr 18 08:46:48 2019
# @author: bsergi

library(ggplot2)
library(openxlsx)
library(plyr)
library(reshape2)

## Working directory and inputs ####
baseWD <- "/Users/Cartographer/GAMS/dispatch_RA-master"
setwd(paste(baseWD, "post_processing", sep="/"))

## Load model results ####
# note: need to change loop to include multiple days when running
processResults <- function(dates, plotTitle){
  setwd(baseWD)
  for(i in 1:length(dates)){
    date <- dates[i]
    dateString <- paste(as.numeric(format(date, "%m")), as.numeric(format(date, "%d")), as.numeric(format(date, "%Y")), sep=".")
    setwd(paste(baseWD, dateString, "results", sep="/"))
    
    # LMP, reserves, and VRE results
    modelLMPtemp <- read.csv("zonal_prices.csv")  
    reservestemp <- read.csv("reserve_segment_commit.csv")
    VRE <- read.csv("renewable_generation.csv")
    dispatchTemp <- read.csv("generator_dispatch.csv")
    modelLMPtemp$date <- date; reservestemp$date <- date; VRE$date <- date; dispatchTemp$date <- date 
    
    
    # zonal loads, ordc shape, and generator types
    setwd(paste(baseWD, dateString, "inputs", sep="/"))
    zonalLoadtemp <- read.csv("timepoints_zonal.csv")
    ordctemp <- read.csv("full_ordc.csv")
    gensTemp <- read.csv("PJM_generators_full.csv")
    gensTemp <- gensTemp[,c("Name", "Zone", "Category")]  # subset generator columns
    
    zonalLoadtemp$date <- date; ordctemp$date <- date
    
    if(i == 1){
      modelLMP <- modelLMPtemp
      reserves <- reservestemp
      dispatch <- dispatchTemp
      
      zonalLoad <- zonalLoadtemp
      ordc <- ordctemp
      gens <- gensTemp
    } else{
      modelLMP <- rbind(modelLMP, modelLMPtemp)
      reserves <- rbind(reserves, reservestemp)
      zonalLoad <- rbind(zonalLoad, zonalLoadtemp)
      ordc <- rbind(ordc, ordctemp)
      dispatch <- rbind(dispatch, dispatchTemp)
      
      gens <- rbind(gens, gensTemp)
      # remove duplicate generations
      gens <- gens[!duplicated(gens),]
    }
    rm(modelLMPtemp); rm(reservestemp); rm(zonalLoadtemp); rm(ordctemp); rm(gensTemp)
  }
  
  
  # subset to reserve segments 1-10 and hours 1-24
  ordc_segments <- 10
  hours <- 24
  
  plotLMPs(dates, modelLMP, zonalLoad, plotTitle)
  plotReserves(ordc_segments, hours, dates, reserves, ordc, plotTitle)
  plotDispatch(dates, dispatch, VRE, gens, hours, plotTitle)
}

## LMPs ####

readPJM_LMPs <- function(dates){
  setwd(paste(baseWD, "post_processing", sep="/"))
  reportedLMPs <- read.csv("lmp_historical.csv")
  reportedLMPs$datetime <- as.POSIXct(reportedLMPs[,"Local.Datetime..Hour.Ending."], format="%m/%d/%y %H:%M")
  reportedLMPs$date <-format(reportedLMPs$datetime, "%m-%d-%y")
  reportedLMPs$hour <- as.numeric(format(reportedLMPs$datetime, "%H"))
  
  reportedLMPsub <- reportedLMPs[reportedLMPs$date %in% format(dates, "%m-%d-%y"),]
  reportedLMPsub$date <- as.POSIXct(reportedLMPsub$date, format="%m-%d-%y")
  return(reportedLMPsub)
}

loadNoORDC <- function(dates){
  
  setwd(baseWD)
  for(i in 1:length(dates)){
    date <- dates[i]
    dateString <- paste(as.numeric(format(date, "%m")), as.numeric(format(date, "%d")), as.numeric(format(date, "%Y")), sep=".")
    setwd(paste(baseWD, "No ORDC input files", dateString, "results", sep="/"))
    
    # LMP and zonal loads for no_ordc case
    modelLMPtemp <- read.csv("zonal_prices.csv")  
    modelLMPtemp$date <- date

    setwd(paste(baseWD, "No ORDC input files", dateString, "inputs", sep="/"))
    zonalLoadtemp <- read.csv("timepoints_zonal.csv")
    zonalLoadtemp$date <- date
    
    if(i == 1){
      modelLMP <- modelLMPtemp
      zonalLoad <- zonalLoadtemp
    } else{
      modelLMP <- rbind(modelLMP, modelLMPtemp)
      zonalLoad <- rbind(zonalLoad, zonalLoadtemp)
    }
  }
  
  #formatting of model LMP
  colnames(modelLMP)[1] <- "Node"
  
  modelLMP <- merge(modelLMP, zonalLoad[,c("date", "timepoint", "zone", "gross_load")], 
                    by.x=c("date", "hour", "Node"), by.y=c("date", "timepoint", "zone"), all=T, sort=F)
  
  # calculated weighted average across zones for PJM-wide LMP
  PJM_LMP <- ddply(modelLMP, ~ date + hour, summarize, LMP = sum(gross_load * LMP / sum(gross_load)), gross_load = sum(gross_load))
  PJM_LMP$Node <- "PJM"
  PJM_LMP <- PJM_LMP[,c("date", "hour", "Node", "LMP", "gross_load")]
  
  modelLMP <- rbind(modelLMP, PJM_LMP)
  modelLMP$Node <- mapvalues(modelLMP$Node, from=c("DC_BGE_PEP", "PA_METED_PPL"), to=c("BGE", "PPL"))

  
  # merge reported and modeled data
  modelLMP$source <- "model: no ORDC"
  modelLMP$datetime <- with(modelLMP, paste(date, hour))
  modelLMP$datetime <- as.POSIXct(modelLMP$datetime, format = "%Y-%m-%d %H")
  
  return(modelLMP)
  
}

plotLMPs <- function(dates, modelLMP, zonalLoad, plotTitle){
  
  reportedLMPsub <- readPJM_LMPs(dates)
  
  #formatting of model LMP
  colnames(modelLMP)[1] <- "Node"
  
  modelLMP <- merge(modelLMP, zonalLoad[,c("date", "timepoint", "zone", "gross_load")], 
                    by.x=c("date", "hour", "Node"), by.y=c("date", "timepoint", "zone"), all=T, sort=F)
  
  # calculated weighted average across zones for PJM-wide LMP
  PJM_LMP <- ddply(modelLMP, ~ date + hour, summarize, LMP = sum(gross_load * LMP / sum(gross_load)), gross_load = sum(gross_load))
  PJM_LMP$Node <- "PJM"
  PJM_LMP <- PJM_LMP[,c("date", "hour", "Node", "LMP", "gross_load")]
  
  modelLMP <- rbind(modelLMP, PJM_LMP)
  modelLMP$Node <- mapvalues(modelLMP$Node, from=c("DC_BGE_PEP", "PA_METED_PPL"), to=c("BGE", "PPL"))
  
  reportedLMPsub <- reportedLMPsub[, c("date", "hour", "Price.Node.Name", "Price...MWh")]
  reportedLMPsub$gross_load <- NA
  colnames(reportedLMPsub) <- c("date", "hour", "Node", "LMP", "gross_load")
  reportedLMPsub$Node <- mapvalues(reportedLMPsub$Node, 
                                   from=c("PJM-RTO ZONE", "DOMINION HUB", "EASTERN HUB", "WESTERN HUB"), 
                                   to=c("PJM", "VA_DOM", "EAST", "WEST"))
  
  # merge reported and modeled data
  modelLMP$source <- "model"
  reportedLMPsub$source <- "reported"
  
  fullLMP <- rbind(modelLMP, reportedLMPsub)
  
  fullLMP$datetime <- with(fullLMP, paste(date, hour))
  fullLMP$datetime <- as.POSIXct(fullLMP$datetime, format = "%Y-%m-%d %H")
  
  fullLMP$source <- mapvalues(fullLMP$source, from="model", to="model: ORDC")
  noORDCresults <- loadNoORDC(dates)
  fullLMP <- rbind(fullLMP, noORDCresults)
  
  # truncate
  ggplot(data=fullLMP, aes(x=datetime, y=LMP, colour=Node, linetype=source)) + facet_wrap(~Node) +
    geom_line() + theme_classic() + xlab("") + ylab("LMP ($ per MWh)") + 
    guides(colour=guide_legend(title="Zone"),
           linetype=guide_legend(title="")) + #coord_cartesian(ylim=c(0, 2000)) +
    scale_linetype_manual(values=c(2,3,1)) +
    theme(text=element_text(size=12),
          axis.text=element_text(size=10))
  
  setwd(paste(baseWD, "post_processing", "figures", sep="/"))
  ggsave(paste0("LMPs ", plotTitle, ".png"), width=10, height=6)
  
}

## Reserve pricing ####

# reformat and merge (add to function later)
plotReserves <- function(ordc_segments, hours, dates, reserves, ordc, plotTitle){
  reserve_set <- as.data.frame(expand.grid(segment=1:ordc_segments, hour=1:hours))
  reserve_set <- reserve_set[with(reserve_set, order(segment, hour)),]
  reserve_set$set <- factor(with(reserve_set, paste(segment, hour, sep=",")))
  
  reserves <- reserves[reserves$X %in% reserve_set$set,]
  reserves$timepoint <- rep(1:hours, ordc_segments*length(dates))
  reserves$segments <- rep(rep(1:ordc_segments, each=hours), length(dates))
  #reserves <- merge(reserves, reserve_set, by.x="X", by.y="segment", all=T)
  reserves$X <- NULL
  
  reserves <- merge(reserves, ordc, by=c("date", "timepoint", "segments"), all.x=T)
  reserves <- reserves[with(reserves, order(date, timepoint, segments)),]
  
  reserves <- ddply(reserves, ~ date + timepoint, transform, 
                    cumulativeReserve = cumsum(MW),
                    cumulativeProcured = cumsum(MW.on.reserve.segment),
                    procured = sum(MW.on.reserve.segment))
  
  reserves$priceFlag <- ifelse(reserves$procured > reserves$cumulativeReserve | reserves$MW.on.reserve.segment == 0, F, T)
  
  reserves$datetime <- with(reserves, paste(date, timepoint))
  reserves$datetime <- as.POSIXct(reserves$datetime, format = "%Y-%m-%d %H")
  procured <- reserves[reserves$priceFlag,]
  
  # scale for secondary price axis
  scale <- max(procured$Price) / max(reserves$cumulativeProcured) 
  
  ggplot(reserves, aes(x=datetime, y=MW.on.reserve.segment, fill=segments)) + geom_bar(stat='identity', size=0) +
    geom_line(data=procured, aes(x=datetime, y=Price/scale ), colour='red') +
    #geom_point(data=procured, aes(x=timepoint, y=Price*scale), colour='red', shape=4) +
    scale_y_continuous(sec.axis = sec_axis(~.*scale, name="Reserve price ($ per MW)")) + 
    coord_cartesian(ylim=c(0, max(reserves$cumulativeProcured)*1.05)) +
    xlab("") + ylab("Reserves procured (MW)") + 
    guides(fill=guide_legend(title="ORDC\nsegment"),
           shape=guide_legend()) +
    scale_fill_gradient(breaks=rev(c(1:10))) + theme_classic() + 
    theme(text=element_text(size=12),
          axis.text=element_text(size=10))
  
  setwd(paste(baseWD, "post_processing", "figures", sep="/"))
  ggsave(paste0("Reserves ", plotTitle, ".png"), width=10)
  
}

## Generation dispatch ####

plotDispatch <- function(dates, dispatch, VRE, gens, hours, plotTitle){
  # subset dispatch output to single day
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
  
  fuelDispatch 
  fuelDispatch$Category <- droplevels(fuelDispatch$Category)
  
  ggplot(data=fuelDispatch, aes(x=datetime, y=MW/1E3, fill=Category)) + geom_area() + facet_wrap(~zone, nrow=3, scales = "free") + 
    theme_classic() + ylab("GW") + guides(fill=guide_legend(title="")) + xlab("") +
    scale_x_datetime() +
    ggtitle(paste("Generation by fuel for", plotTitle))
  
  setwd(paste(baseWD, "post_processing", "figures", sep="/"))
  ggsave(paste0("dispatch ", plotTitle, ".png"), width=12, height=12)
  
  setwd(paste(baseWD, "post_processing", sep="/"))
  save.image("~/GAMS/dispatch_RA-master/post_processing/Results both ORDC.RData")
}

## Main ####
dates <- seq(as.POSIXct("1/4/2014", format = "%m/%d/%Y"), by="day", length.out=7)
processResults(dates, plotTitle="Jan. 4-10, 2014")

dates <- seq(as.POSIXct("10/19/2017", format = "%m/%d/%Y"), by="day", length.out=7)
processResults(dates, plotTitle="Oct 19-25, 2017")

